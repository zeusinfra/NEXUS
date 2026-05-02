import 'dart:async';
import 'dart:collection';
import 'dart:convert';
import 'dart:math';

import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

enum ZeusConnectionState { disconnected, connecting, connected }

class ZeusEvent {
  ZeusEvent({
    required this.type,
    required this.payload,
    required this.timestamp,
    this.eventId,
    this.ack = false,
  });

  final String type;
  final Map<String, dynamic> payload;
  final DateTime timestamp;
  final String? eventId;
  final bool ack;

  factory ZeusEvent.fromJson(Map<String, dynamic> map) {
    return ZeusEvent(
      type: map['type']?.toString() ?? 'unknown',
      payload: (map['payload'] as Map?)?.cast<String, dynamic>() ?? map,
      timestamp: DateTime.tryParse(map['timestamp']?.toString() ?? '') ??
          DateTime.now().toUtc(),
      eventId: map['event_id']?.toString(),
      ack: map['type']?.toString() == 'ack',
    );
  }
}

class ZeusGatewayService {
  ZeusGatewayService(
      {required this.wsUrl, required this.httpUrl, this.authToken});

  final Uri wsUrl;
  final Uri httpUrl;
  final String? authToken;

  final Queue<Map<String, dynamic>> _offlineQueue =
      Queue<Map<String, dynamic>>();
  final Map<String, Completer<void>> _pendingAcks = {};

  WebSocketChannel? _channel;
  Timer? _reconnectTimer;
  Timer? _heartbeatTimer;
  Timer? _healthTimer;
  bool _manualDisconnect = false;
  int _reconnectAttempt = 0;

  final StreamController<ZeusEvent> _eventsController =
      StreamController.broadcast();
  final StreamController<ZeusConnectionState> _connectionController =
      StreamController.broadcast();
  final StreamController<List<Map<String, dynamic>>> _historyController =
      StreamController.broadcast();
  final List<Map<String, dynamic>> _history = [];

  ZeusConnectionState _connectionState = ZeusConnectionState.disconnected;

  Stream<ZeusEvent> get events => _eventsController.stream;
  Stream<ZeusConnectionState> get connectionState =>
      _connectionController.stream;
  Stream<List<Map<String, dynamic>>> get history => _historyController.stream;

  Future<void> connect() async {
    _manualDisconnect = false;
    _startHealthPolling();
    await _openSocket();
  }

  Future<void> _openSocket() async {
    _setConnectionState(ZeusConnectionState.connecting);
    try {
      final url = authToken == null
          ? wsUrl
          : wsUrl.replace(
              queryParameters: {...wsUrl.queryParameters, 'token': authToken});

      _channel = WebSocketChannel.connect(url);
      _setConnectionState(ZeusConnectionState.connected);
      _reconnectAttempt = 0;
      await _flushQueue();

      _channel!.stream.listen((dynamic data) {
        try {
          final decoded = jsonDecode(data.toString()) as Map<String, dynamic>;
          final event = ZeusEvent.fromJson(decoded);
          _eventsController.add(event);
          if (event.ack &&
              event.eventId != null &&
              _pendingAcks.containsKey(event.eventId)) {
            _pendingAcks.remove(event.eventId)?.complete();
          }
          _appendMessageFromServer(decoded);
        } catch (_) {}
      },
          onDone: _handleSocketDrop,
          onError: (_) => _handleSocketDrop(),
          cancelOnError: true);

      _startHeartbeat();
    } catch (_) {
      _handleSocketDrop();
    }
  }

  void _handleSocketDrop() {
    _heartbeatTimer?.cancel();
    _channel = null;
    _setConnectionState(ZeusConnectionState.disconnected);
    if (_manualDisconnect) return;

    _reconnectAttempt += 1;
    final seconds = min(30, pow(2, _reconnectAttempt).toInt());
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(Duration(seconds: seconds), _openSocket);
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 20), (_) {
      if (_channel != null) {
        _channel!.sink.add(jsonEncode({
          'version': '1.0',
          'type': 'ping',
          'timestamp': DateTime.now().toUtc().toIso8601String(),
          'payload': const {},
        }));
      }
    });
  }

  void _startHealthPolling() {
    _healthTimer?.cancel();
    _checkHttpHealth();
    _healthTimer = Timer.periodic(
      const Duration(seconds: 10),
      (_) => _checkHttpHealth(),
    );
  }

  Future<void> _checkHttpHealth() async {
    try {
      final healthUrl = httpUrl.replace(path: '/api/health', query: '');
      final response =
          await http.get(healthUrl).timeout(const Duration(seconds: 3));
      if (response.statusCode >= 200 && response.statusCode < 300) {
        if (_connectionState == ZeusConnectionState.disconnected) {
          _setConnectionState(ZeusConnectionState.connected);
        }
      } else if (_channel == null) {
        _setConnectionState(ZeusConnectionState.disconnected);
      }
    } catch (_) {
      if (_channel == null) {
        _setConnectionState(ZeusConnectionState.disconnected);
      }
    }
  }

  Future<void> sendUserInput(String text) async {
    final eventId = '${DateTime.now().microsecondsSinceEpoch}';
    final payload = {
      'version': '1.0',
      'event_id': eventId,
      'timestamp': DateTime.now().toUtc().toIso8601String(),
      'source': 'zeus_bubble_linux',
      'type': 'user_input',
      'payload': {'text': text},
    };

    _appendHistory({'role': 'user', 'content': text});
    if (_channel != null && _connectionState == ZeusConnectionState.connected) {
      _channel!.sink.add(jsonEncode(payload));
      final c = Completer<void>();
      _pendingAcks[eventId] = c;
      try {
        await c.future.timeout(const Duration(seconds: 5));
      } catch (_) {
        _offlineQueue.add(payload);
      }
      return;
    }

    _offlineQueue.add(payload);
    await _tryHttpFallback(payload);
  }

  Future<void> _flushQueue() async {
    while (_offlineQueue.isNotEmpty && _channel != null) {
      final item = _offlineQueue.removeFirst();
      _channel!.sink.add(jsonEncode(item));
    }
  }

  Future<void> _tryHttpFallback(Map<String, dynamic> payload) async {
    try {
      final text = ((payload['payload'] as Map?)?['text'] ?? '').toString();
      if (text.isEmpty ||
          text == '__voice_start__' ||
          text == '__vision_analyze__') {
        return;
      }

      final response = await http
          .post(
            httpUrl,
            headers: {
              'Content-Type': 'application/json',
              if (authToken != null) 'Authorization': 'Bearer $authToken',
            },
            body: jsonEncode({
              'message': text,
              'client_msg_id': payload['event_id']?.toString(),
              'source': 'zeus_bubble_linux',
              'client_id': 'zeus_bubble_linux',
            }),
          )
          .timeout(const Duration(seconds: 10));
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final decoded = jsonDecode(response.body);
        if (decoded is Map<String, dynamic>) {
          final reply = decoded['reply']?.toString();
          if (reply != null && reply.isNotEmpty) {
            _appendHistory({'role': 'assistant', 'content': reply});
          }
        }
      }
    } catch (_) {}
  }

  void _appendMessageFromServer(Map<String, dynamic> decoded) {
    final type = decoded['type']?.toString();
    if (type == 'ack' || type == 'pong' || type == 'init') return;

    final payload = (decoded['payload'] as Map?)?.cast<String, dynamic>();
    final message =
        decoded['message']?.toString() ?? payload?['message']?.toString();
    if (message == null || message.isEmpty) return;

    if (type == 'CHAT_USER') {
      _appendHistory({'role': 'user', 'content': message});
    } else if (type == 'CHAT_AI' || type == 'assistant_message') {
      _appendHistory({'role': 'assistant', 'content': message});
    }
  }

  void _appendHistory(Map<String, dynamic> msg) {
    _history.add(msg);
    if (_history.length > 100) _history.removeAt(0);
    _historyController.add(List.unmodifiable(_history));
  }

  void _setConnectionState(ZeusConnectionState state) {
    _connectionState = state;
    _connectionController.add(state);
  }

  Future<void> dispose() async {
    _manualDisconnect = true;
    _reconnectTimer?.cancel();
    _heartbeatTimer?.cancel();
    _healthTimer?.cancel();
    await _channel?.sink.close();
    await _eventsController.close();
    await _connectionController.close();
    await _historyController.close();
  }
}

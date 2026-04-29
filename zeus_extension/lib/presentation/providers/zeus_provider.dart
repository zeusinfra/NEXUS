import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../data/zeus_api_client.dart';
import '../../data/zeus_websocket_client.dart';
import '../../data/voice_service.dart';
import '../../data/firebase_messaging_service.dart';
import '../../domain/models.dart';

class ZeusState {
  final List<ZeusMessage> chatHistory;
  final SystemStatus? status;
  final bool isConnected;
  final bool isListening;
  final bool isThinking;
  final String partialSpeech;
  final String lastStatus;
  final String streamingText;

  ZeusState({
    this.chatHistory = const [],
    this.status,
    this.isConnected = false,
    this.isListening = false,
    this.isThinking = false,
    this.partialSpeech = '',
    this.lastStatus = '',
    this.streamingText = '',
  });

  ZeusState copyWith({
    List<ZeusMessage>? chatHistory,
    SystemStatus? status,
    bool? isConnected,
    bool? isListening,
    bool? isThinking,
    String? partialSpeech,
    String? lastStatus,
    String? streamingText,
  }) {
    return ZeusState(
      chatHistory: chatHistory ?? this.chatHistory,
      status: status ?? this.status,
      isConnected: isConnected ?? this.isConnected,
      isListening: isListening ?? this.isListening,
      isThinking: isThinking ?? this.isThinking,
      partialSpeech: partialSpeech ?? this.partialSpeech,
      lastStatus: lastStatus ?? this.lastStatus,
      streamingText: streamingText ?? this.streamingText,
    );
  }
}

class ZeusNotifier extends StateNotifier<ZeusState> {
  ZeusWebSocketClient _wsClient = ZeusWebSocketClient();
  StreamSubscription<Map<String, dynamic>>? _wsSub;
  final VoiceService _voiceService = VoiceService();
  late ZeusApiClient _apiClient;
  
  ZeusNotifier() : super(ZeusState()) {
    _wsSub = _wsClient.messages.listen(_handleIncomingMessage);
    _voiceService.setTtsCompletionHandler(() {
      // Auto-activation: listen again after speaking
      toggleListening();
    });
    _init();
  }

  void _resetWsClient() {
    try {
      _wsSub?.cancel();
    } catch (_) {}
    try {
      _wsClient.dispose();
    } catch (_) {}

    _wsClient = ZeusWebSocketClient();
    _wsSub = _wsClient.messages.listen(_handleIncomingMessage);
  }

  Future<void> _init() async {
    final prefs = await SharedPreferences.getInstance();
    final savedUrl = prefs.getString('zeus_base_url') ?? "http://localhost:8080";
    _apiClient = ZeusApiClient(baseUrl: savedUrl);
    await _apiClient.loadSavedSession();
    
    if (_apiClient.token != null) {
      final wsUrl = _toWsBase(savedUrl);
      connect(wsUrl, _apiClient.token!, lanToken: _apiClient.lanToken);
    }
  }

  Future<bool> login(String url, String token, {String? lanToken}) async {
    _apiClient = ZeusApiClient(baseUrl: url);
    final success = await _apiClient.login(zeusToken: token, lanToken: lanToken);
    if (success) {
      final wsUrl = _toWsBase(url);
      connect(wsUrl, _apiClient.token!, lanToken: _apiClient.lanToken);
      return true;
    }
    return false;
  }

  String _toWsBase(String httpBase) {
    if (httpBase.startsWith("https://")) return httpBase.replaceFirst("https://", "wss://");
    if (httpBase.startsWith("http://")) return httpBase.replaceFirst("http://", "ws://");
    return httpBase;
  }

  void connect(String wsBaseUrl, String token, {String? lanToken}) async {
    _resetWsClient();
    final wsMobileUrl = "$wsBaseUrl/ws/mobile";
    _wsClient.connect(wsMobileUrl, jwt: token, lanToken: lanToken);
    state = state.copyWith(isConnected: true);
    
    final fcmService = FirebaseMessagingService();
    await fcmService.init();
    final fcmToken = await fcmService.getToken();
    if (fcmToken != null) {
      _wsClient.send("device_register", {
        "device_id": "mobile_device",
        "fcm_token": fcmToken
      });
    }
  }

  void logout() async {
    await _apiClient.logout();
    _resetWsClient();
    state = ZeusState();
  }

  void sendMessage(String text) {
    state = state.copyWith(isThinking: true, streamingText: '');
    _wsClient.send("chat", {"text": text});
  }

  void sendMicMessageForNotebookVoice(String text) {
    state = state.copyWith(isThinking: true, streamingText: '');
    _wsClient.send("chat", {
      "text": text,
      "source": "mobile_mic",
      "silent_mobile_tts": true,
    });
  }

  void sendCommand(String cmd) {
    _wsClient.send("command", {"text": cmd});
  }

  void executeSystemAction(String command) {
    _wsClient.send("system_control", {
      "action": "execute_command",
      "command": command
    });
  }

  void toggleListening() {
    if (_voiceService.isListening) {
      _voiceService.stopListening();
      state = state.copyWith(isListening: false, partialSpeech: '');
    } else {
      state = state.copyWith(isListening: true, partialSpeech: '');
      _voiceService.startListening((text, isFinal) {
        if (isFinal) {
          state = state.copyWith(isListening: false, partialSpeech: '');
          if (text.isNotEmpty) {
            // Modo extensao: microfone do app envia comando para resposta falada no notebook.
            sendMicMessageForNotebookVoice(text);
          }
        } else {
          state = state.copyWith(partialSpeech: text);
        }
      });
    }
  }

  void _handleIncomingMessage(Map<String, dynamic> msg) {
    final type = msg['type'];
    if (type == 'HUD_STATUS') {
      state = state.copyWith(lastStatus: msg['text'] ?? msg['message'] ?? "");
    } else if (type == 'CHUNK_AI') {
      final chunk = msg['chunk'] ?? "";
      state = state.copyWith(streamingText: state.streamingText + chunk);
    } else if (type == 'CHAT_AI' || type == 'CHAT_USER') {
      if (type == 'CHAT_AI') {
        state = state.copyWith(isThinking: false, streamingText: '');
      }
      final newMessage = ZeusMessage.fromJson(msg);
      final next = [...state.chatHistory, newMessage];
      const maxHistory = 500;
      state = state.copyWith(chatHistory: next.length > maxHistory ? next.sublist(next.length - maxHistory) : next);
    } else if (type == 'voice' || type == 'voice_play') {
      final target = msg['target'] ?? msg['payload']?['target'];
      if (target == 'notebook') {
        return;
      }
      final text = msg['payload']?['text'] ?? msg['text'] ?? "";
      if (text.isNotEmpty) {
        _voiceService.speak(text);
      }
    } else if (type == 'AUDIO_RESPONSE') {
      final audio = msg['audio'] ?? "";
      if (audio.isNotEmpty) {
        _voiceService.playBase64Audio(audio);
      }
    } else if (type == 'pong') {
      // Keep-alive response from backend; no UI mutation needed.
    } else if (type == 'METRICS') {
      final cpuRaw = msg['cpu'];
      double cpu = 0;
      if (cpuRaw is List && cpuRaw.isNotEmpty) {
        cpu = cpuRaw.map((e) => (e is num ? e.toDouble() : 0.0)).reduce((a, b) => a + b) / cpuRaw.length;
      } else if (cpuRaw is num) {
        cpu = cpuRaw.toDouble();
      }
      final ram = (msg['ram'] ?? 0.0) is num ? (msg['ram'] as num).toDouble() : 0.0;
      final mood = msg['behavioral_state'] ?? 'IDLE';
      final events = msg['total_events'] ?? 0;
      state = state.copyWith(
        status: SystemStatus(cpu: cpu, ram: ram, mood: mood, activeTasks: events is int ? events : 0),
      );
    }
  }

  @override
  void dispose() {
    try {
      _wsSub?.cancel();
    } catch (_) {}
    _wsClient.dispose();
    super.dispose();
  }
}

final zeusProvider = StateNotifierProvider<ZeusNotifier, ZeusState>((ref) => ZeusNotifier());

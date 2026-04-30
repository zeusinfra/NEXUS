import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../domain/bubble_state.dart';
import '../../domain/zeus_config.dart';
import '../../services/zeus_gateway_service.dart';

const _wsKey = 'zeus_ws_url';
const _httpKey = 'zeus_http_url';
const _tokenKey = 'zeus_auth_token';

final zeusConfigProvider =
    StateNotifierProvider<ZeusConfigController, ZeusConfig>((_) {
  return ZeusConfigController()..load();
});

final zeusGatewayProvider = Provider<ZeusGatewayService>((ref) {
  final config = ref.watch(zeusConfigProvider);
  final service = ZeusGatewayService(
    wsUrl: Uri.parse(config.wsUrl),
    httpUrl: Uri.parse(config.httpUrl),
    authToken: config.token,
  );

  ref.onDispose(service.dispose);
  return service;
});

final connectionStateProvider =
    StateProvider<ZeusConnectionState>((_) => ZeusConnectionState.disconnected);

final chatHistoryProvider = StateProvider<List<Map<String, dynamic>>>((_) => const []);

final bubbleStateProvider =
    StateNotifierProvider<BubbleStateController, BubbleState>((ref) {
  final controller = BubbleStateController(
    ref.read(zeusGatewayProvider),
    ref.read(connectionStateProvider.notifier),
    ref.read(chatHistoryProvider.notifier),
  );
  ref.onDispose(controller.dispose);
  return controller;
});

class ZeusConfigController extends StateNotifier<ZeusConfig> {
  ZeusConfigController() : super(ZeusConfig.defaults());

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    state = ZeusConfig(
      wsUrl: prefs.getString(_wsKey) ?? ZeusConfig.defaults().wsUrl,
      httpUrl: prefs.getString(_httpKey) ?? ZeusConfig.defaults().httpUrl,
      token: prefs.getString(_tokenKey),
    );
  }

  Future<void> save(ZeusConfig config) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_wsKey, config.wsUrl);
    await prefs.setString(_httpKey, config.httpUrl);
    if (config.token == null || config.token!.isEmpty) {
      await prefs.remove(_tokenKey);
    } else {
      await prefs.setString(_tokenKey, config.token!);
    }
    state = config;
  }
}

class BubbleStateController extends StateNotifier<BubbleState> {
  BubbleStateController(this._gateway, this._connectionStateNotifier, [this._historyState])
      : super(BubbleState.idle) {
    _init();
  }

  final ZeusGatewayService _gateway;
  final StateController<ZeusConnectionState> _connectionStateNotifier;
  final StateController<List<Map<String, dynamic>>>? _historyState;
  StreamSubscription<ZeusEvent>? _eventSubscription;
  StreamSubscription<ZeusConnectionState>? _connectionSubscription;

  Future<void> _init() async {
    _connectionStateNotifier.state = ZeusConnectionState.connecting;
    await _gateway.connect();
    _eventSubscription = _gateway.events.listen(_onEvent);
    _connectionSubscription = _gateway.connectionState.listen((state) {
      _connectionStateNotifier.state = state;
    });
    _gateway.history.listen((h) {
      _historyState?.state = h;
    });
  }

  Future<void> activateListening() async {
    state = BubbleState.listening;
    await _gateway.sendUserInput('__voice_start__');
  }

  Future<void> sendText(String text) async {
    if (text.trim().isEmpty) return;
    state = BubbleState.thinking;
    await _gateway.sendUserInput(text);
  }

  void _onEvent(ZeusEvent event) {
    switch (event.type) {
      case 'thinking':
        state = BubbleState.thinking;
        break;
      case 'speaking':
        state = BubbleState.speaking;
        break;
      case 'listening':
        state = BubbleState.listening;
        break;
      case 'idle':
        state = BubbleState.idle;
        break;
      default:
        break;
    }
  }

  @override
  void dispose() {
    _eventSubscription?.cancel();
    _connectionSubscription?.cancel();
    super.dispose();
  }
}

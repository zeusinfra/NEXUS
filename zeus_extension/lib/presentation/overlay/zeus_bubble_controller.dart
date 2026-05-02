import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../data/voice_service.dart';
import '../../domain/bubble_state.dart';
import '../../domain/zeus_config.dart';
import '../../services/zeus_gateway_service.dart';

const _wsKey = 'zeus_ws_url';
const _httpKey = 'zeus_http_url';
const _tokenKey = 'zeus_auth_token';

final voiceServiceProvider = Provider<VoiceService>((ref) {
  final service = VoiceService();
  service.init();
  return service;
});

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

final chatHistoryProvider =
    StateProvider<List<Map<String, dynamic>>>((_) => const []);

final bubbleStateProvider =
    StateNotifierProvider<BubbleStateController, BubbleState>((ref) {
  return BubbleStateController(
    ref.read(zeusGatewayProvider),
    ref.read(connectionStateProvider.notifier),
    ref.read(voiceServiceProvider),
    ref.read(chatHistoryProvider.notifier),
  );
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
  BubbleStateController(
      this._gateway, this._connectionStateNotifier, this._voiceService,
      [this._historyState])
      : super(BubbleState.idle) {
    Future.microtask(_init);
  }

  final ZeusGatewayService _gateway;
  final StateController<ZeusConnectionState> _connectionStateNotifier;
  final VoiceService _voiceService;
  final StateController<List<Map<String, dynamic>>>? _historyState;
  StreamSubscription<ZeusEvent>? _eventSubscription;
  StreamSubscription<ZeusConnectionState>? _connectionSubscription;
  StreamSubscription<List<Map<String, dynamic>>>? _historySubscription;

  Future<void> _init() async {
    if (!mounted) return;
    _connectionStateNotifier.state = ZeusConnectionState.connecting;
    await _gateway.connect();
    if (!mounted) return;
    _eventSubscription = _gateway.events.listen(_onEvent);
    _connectionSubscription = _gateway.connectionState.listen((state) {
      if (!mounted) return;
      _connectionStateNotifier.state = state;
    });
    _historySubscription = _gateway.history.listen((h) {
      if (!mounted) return;
      _historyState?.state = h;
    });
  }

  Future<void> activateListening() async {
    if (!mounted) return;
    state = BubbleState.listening;
    await _gateway.sendUserInput('__voice_start__');
  }

  Future<void> sendText(String text) async {
    if (text.trim().isEmpty) return;
    if (!mounted) return;
    state = BubbleState.thinking;
    await _gateway.sendUserInput(text);
  }

  Future<void> requestVisionAnalysis() async {
    if (!mounted) return;
    state = BubbleState.thinking;
    await _gateway.sendUserInput('__vision_analyze__');
  }

  void _onEvent(ZeusEvent event) {
    if (!mounted) return;
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
      case 'voice_play':
        state = BubbleState.speaking;
        if (event.payload['audio'] != null) {
          _voiceService.playBase64Audio(event.payload['audio'] as String);
        } else if (event.payload['text'] != null) {
          _voiceService.speak(event.payload['text'] as String);
        }
        break;

      // --- Voice Sensing Pipeline Events ---
      case 'VOICE_STATE':
        final stage = event.payload['stage']?.toString() ?? '';
        switch (stage) {
          case 'listening':
            state = BubbleState.listening;
            break;
          case 'transcribing':
            state = BubbleState.thinking;
            break;
          case 'speaking':
            state = BubbleState.speaking;
            break;
          case 'idle':
            state = BubbleState.idle;
            break;
        }
        break;

      case 'AUDIO_RESPONSE':
        // Backend TTS audio chunk (base64 MP3)
        final audio = event.payload['audio']?.toString();
        if (audio != null && audio.isNotEmpty) {
          state = BubbleState.speaking;
          _voiceService.playBase64Audio(audio);
        }
        break;

      case 'HUD_STATUS':
        // Status updates — detect cognitive processing
        final text = event.payload['text']?.toString() ?? '';
        if (text.contains('processando') || text.contains('cognitivo')) {
          state = BubbleState.thinking;
        } else if (text.contains('Aguardando')) {
          state = BubbleState.idle;
        }
        break;

      case 'CHAT_AI':
        // AI response received — return to idle after a delay
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
    _historySubscription?.cancel();
    super.dispose();
  }
}

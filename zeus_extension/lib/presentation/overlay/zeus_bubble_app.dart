import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hotkey_manager/hotkey_manager.dart';
import 'package:window_manager/window_manager.dart';

import '../../data/voice_service.dart';
import '../../domain/bubble_state.dart';
import '../../domain/zeus_config.dart';
import '../../services/zeus_gateway_service.dart';
import 'zeus_bubble_controller.dart';

class ZeusBubbleApp extends StatelessWidget {
  const ZeusBubbleApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: ThemeData.dark(),
        home: const ZeusBubbleOverlay(),
      );
}

class ZeusBubbleOverlay extends ConsumerStatefulWidget {
  const ZeusBubbleOverlay({super.key});
  @override
  ConsumerState<ZeusBubbleOverlay> createState() => _State();
}

class _State extends ConsumerState<ZeusBubbleOverlay>
    with SingleTickerProviderStateMixin {
  final VoiceService _voiceService = VoiceService();
  late AnimationController _animController;
  late Animation<double> _breatheAnim;
  final HotKey _hotKey = HotKey(
    key: LogicalKeyboardKey.space,
    modifiers: [HotKeyModifier.alt],
    scope: HotKeyScope.system,
  );
  final HotKey _visionHotKey = HotKey(
    key: LogicalKeyboardKey.keyV,
    modifiers: [HotKeyModifier.alt],
    scope: HotKeyScope.system,
  );

  @override
  void initState() {
    super.initState();
    _voiceService.init();

    _animController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);

    _breatheAnim = Tween<double>(begin: 0.95, end: 1.05).animate(
      CurvedAnimation(parent: _animController, curve: Curves.easeInOut),
    );

    _initHotkeys();
  }

  Future<void> _initHotkeys() async {
    await hotKeyManager.register(
      _hotKey,
      keyDownHandler: (hotKey) async {
        await windowManager.show();
        await windowManager.focus();
        _startVoice();
      },
    );
    await hotKeyManager.register(
      _visionHotKey,
      keyDownHandler: (hotKey) async {
        await windowManager.show();
        await windowManager.focus();
        _startVision();
      },
    );
  }

  @override
  void dispose() {
    hotKeyManager.unregister(_hotKey);
    hotKeyManager.unregister(_visionHotKey);
    _animController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(bubbleStateProvider);
    final conn = ref.watch(connectionStateProvider);

    // Ajusta a velocidade da animação com base no estado
    if (state == BubbleState.listening) {
      _animController.duration = const Duration(milliseconds: 600);
      if (!_animController.isAnimating) _animController.repeat(reverse: true);
    } else if (state == BubbleState.thinking) {
      _animController.duration = const Duration(milliseconds: 300);
      if (!_animController.isAnimating) _animController.repeat(reverse: true);
    } else {
      _animController.duration = const Duration(seconds: 2);
      if (!_animController.isAnimating) _animController.repeat(reverse: true);
    }

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Center(
        child: GestureDetector(
          onPanStart: (_) => windowManager.startDragging(),
          onTap: _startVoice,
          onDoubleTap: () => _showChatPanel(context),
          onSecondaryTapDown: (_) => _showMenu(context),
          child: ScaleTransition(
            scale: _breatheAnim,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 280),
              width: _size(state),
              height: _size(state),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(colors: _colors(state)),
                border: Border.all(color: _stateColor(state, conn), width: 2.5),
                boxShadow: [
                  BoxShadow(
                    color: _stateColor(state, conn).withValues(alpha: 0.42),
                    blurRadius: _glow(state),
                    spreadRadius: state == BubbleState.idle ? 2 : 8,
                  ),
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.35),
                    blurRadius: 18,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: Stack(
                alignment: Alignment.center,
                children: [
                  Positioned.fill(
                    child: CustomPaint(
                      painter: _BubbleRingPainter(
                        color: _stateColor(state, conn),
                        state: state,
                      ),
                    ),
                  ),
                  Icon(_stateIcon(state),
                      color: Colors.white.withValues(alpha: 0.86), size: 34),
                  Positioned(
                    bottom: 22,
                    child: Text(
                      _stateLabel(state, conn),
                      style: const TextStyle(
                        color: Colors.white70,
                        fontSize: 9,
                        letterSpacing: 1.2,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ),
                  Positioned(
                    top: 18,
                    right: 24,
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _connColor(conn),
                        boxShadow: [
                          BoxShadow(
                              color: _connColor(conn).withValues(alpha: 0.7),
                              blurRadius: 8),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _startVoice() async {
    // Arm the backend voice sensing (Python captures mic, not Flutter)
    await ref.read(bubbleStateProvider.notifier).activateListening();
  }

  Future<void> _startVision() async {
    await ref.read(bubbleStateProvider.notifier).requestVisionAnalysis();
  }

  Future<void> _showMenu(BuildContext context) async {
    await showModalBottomSheet<void>(
      context: context,
      builder: (_) => SafeArea(
        child: Wrap(children: [
          ListTile(
            leading: const Icon(Icons.visibility),
            title: const Text('👁️ Analisar Tela (Visão)'),
            onTap: () {
              Navigator.pop(context);
              _startVision();
            },
          ),
          ListTile(
            leading: const Icon(Icons.settings),
            title: const Text('Configurar endpoint/token'),
            onTap: () {
              Navigator.pop(context);
              _showConfigDialog(context);
            },
          ),
          ListTile(
            leading: const Icon(Icons.close),
            title: const Text('Fechar bolha'),
            onTap: () => windowManager.close(),
          ),
        ]),
      ),
    );
  }

  Future<void> _showConfigDialog(BuildContext context) async {
    final cfg = ref.read(zeusConfigProvider);
    final ws = TextEditingController(text: cfg.wsUrl);
    final http = TextEditingController(text: cfg.httpUrl);
    final token = TextEditingController(text: cfg.token ?? '');

    await showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Configuração ZEUS'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(
              controller: ws,
              decoration: const InputDecoration(labelText: 'WS URL')),
          TextField(
              controller: http,
              decoration: const InputDecoration(labelText: 'HTTP URL')),
          TextField(
              controller: token,
              decoration: const InputDecoration(labelText: 'Token')),
        ]),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancelar')),
          ElevatedButton(
            onPressed: () async {
              await ref.read(zeusConfigProvider.notifier).save(ZeusConfig(
                    wsUrl: ws.text.trim(),
                    httpUrl: http.text.trim(),
                    token: token.text.trim().isEmpty ? null : token.text.trim(),
                  ));
              if (context.mounted) Navigator.pop(context);
            },
            child: const Text('Salvar'),
          ),
        ],
      ),
    );
  }

  Future<void> _showChatPanel(BuildContext context) async {
    final input = TextEditingController();
    await showDialog<void>(
      context: context,
      builder: (_) {
        final history = ref.watch(chatHistoryProvider);
        return AlertDialog(
          title: const Text('ZEUS Chat'),
          content: SizedBox(
            width: 520,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              SizedBox(
                height: 180,
                child: ListView.builder(
                  itemCount: history.length,
                  itemBuilder: (_, i) =>
                      Text('[${history[i]['role']}] ${history[i]['content']}'),
                ),
              ),
              TextField(controller: input),
            ]),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Cancelar')),
            ElevatedButton(
              onPressed: () async {
                await ref
                    .read(bubbleStateProvider.notifier)
                    .sendText(input.text);
                await _voiceService.speak('Mensagem enviada');
                if (context.mounted) Navigator.pop(context);
              },
              child: const Text('Enviar'),
            ),
          ],
        );
      },
    );
  }

  Color _connColor(ZeusConnectionState s) => s == ZeusConnectionState.connected
      ? Colors.greenAccent
      : s == ZeusConnectionState.connecting
          ? Colors.amberAccent
          : Colors.redAccent;
  double _size(BubbleState s) => s == BubbleState.listening
      ? 124
      : s == BubbleState.thinking
          ? 116
          : s == BubbleState.speaking
              ? 130
              : 108;
  double _glow(BubbleState s) => s == BubbleState.listening
      ? 34
      : s == BubbleState.thinking
          ? 42
          : s == BubbleState.speaking
              ? 38
              : 22;
  IconData _stateIcon(BubbleState s) => s == BubbleState.listening
      ? Icons.mic
      : s == BubbleState.thinking
          ? Icons.psychology
          : s == BubbleState.speaking
              ? Icons.graphic_eq
              : Icons.blur_circular;
  String _stateLabel(BubbleState s, ZeusConnectionState c) {
    if (c == ZeusConnectionState.disconnected) return 'OFFLINE';
    if (c == ZeusConnectionState.connecting) return 'SYNC';
    return s == BubbleState.listening
        ? 'LISTEN'
        : s == BubbleState.thinking
            ? 'THINK'
            : s == BubbleState.speaking
                ? 'SPEAK'
                : 'IDLE';
  }

  Color _stateColor(BubbleState s, ZeusConnectionState c) {
    if (c == ZeusConnectionState.disconnected) return Colors.redAccent;
    if (c == ZeusConnectionState.connecting) return Colors.amberAccent;
    return s == BubbleState.listening
        ? const Color(0xFF00F5D4)
        : s == BubbleState.thinking
            ? const Color(0xFF9B5DE5)
            : s == BubbleState.speaking
                ? const Color(0xFFFEE440)
                : Colors.cyanAccent;
  }

  List<Color> _colors(BubbleState s) => s == BubbleState.listening
      ? [const Color(0xFF00F5D4), const Color(0xFF00BBF9)]
      : s == BubbleState.thinking
          ? [const Color(0xFF9B5DE5), const Color(0xFFF15BB5)]
          : s == BubbleState.speaking
              ? [const Color(0xFFFEE440), const Color(0xFFFB8500)]
              : [const Color(0xFF00FF99), const Color(0xFF0077FF)];
}

class _BubbleRingPainter extends CustomPainter {
  const _BubbleRingPainter({required this.color, required this.state});

  final Color color;
  final BubbleState state;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.shortestSide / 2 - 8;
    final base = Paint()
      ..color = color.withValues(alpha: 0.18)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4;
    canvas.drawCircle(center, radius, base);

    final active = Paint()
      ..color = color.withValues(alpha: 0.72)
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = 3;
    final sweep = state == BubbleState.idle
        ? 1.8
        : state == BubbleState.thinking
            ? 4.2
            : 3.1;
    canvas.drawArc(Rect.fromCircle(center: center, radius: radius), -1.57,
        sweep, false, active);
  }

  @override
  bool shouldRepaint(covariant _BubbleRingPainter oldDelegate) {
    return oldDelegate.color != color || oldDelegate.state != state;
  }
}

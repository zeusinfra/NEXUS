import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hotkey_manager/hotkey_manager.dart';
import 'package:shared_preferences/shared_preferences.dart';
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
  static const _positionXKey = 'zeus_bubble_window_x';
  static const _positionYKey = 'zeus_bubble_window_y';
  static const _edgeMargin = 12.0;
  static const _dragThreshold = 4.0;
  static const _bubbleWindowSize = Size(220, 220);
  static const _chatWindowSize = Size(430, 640);

  final VoiceService _voiceService = VoiceService();
  final TextEditingController _chatInputController = TextEditingController();
  final ScrollController _chatScrollController = ScrollController();
  late AnimationController _animController;
  late Animation<double> _breatheAnim;
  Offset? _dragStartPointer;
  Offset? _dragStartWindow;
  bool _didDrag = false;
  bool _chatOpen = false;
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
    WidgetsBinding.instance.addPostFrameCallback((_) => _restorePosition());
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
    _chatInputController.dispose();
    _chatScrollController.dispose();
    _animController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(bubbleStateProvider);
    final conn = ref.watch(connectionStateProvider);
    final history = ref.watch(chatHistoryProvider);

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
      body: _chatOpen
          ? _buildChatPanel(context, state, conn, history)
          : _buildBubble(context, state, conn),
    );
  }

  Widget _buildBubble(
    BuildContext context,
    BubbleState state,
    ZeusConnectionState conn,
  ) {
    return Center(
      child: GestureDetector(
        onPanStart: _handlePanStart,
        onPanUpdate: _handlePanUpdate,
        onPanEnd: (_) => _snapToNearestEdge(),
        onPanCancel: _snapToNearestEdge,
        onTap: () {
          if (!_didDrag) _startVoice();
          _didDrag = false;
        },
        onDoubleTap: _openChatPanel,
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
                Positioned.fill(
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(
                        color: Colors.white.withValues(alpha: 0.08),
                      ),
                    ),
                  ),
                ),
                Icon(_stateIcon(state),
                    color: Colors.white.withValues(alpha: 0.88), size: 34),
                Positioned(
                  bottom: 20,
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
                  child: _StatusDot(color: _connColor(conn)),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildChatPanel(
    BuildContext context,
    BubbleState state,
    ZeusConnectionState conn,
    List<Map<String, dynamic>> history,
  ) {
    final statusColor = _connColor(conn);
    return Padding(
      padding: const EdgeInsets.all(10),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(24),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: const Color(0xFF0E1117),
            border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.42),
                blurRadius: 28,
                offset: const Offset(0, 18),
              ),
            ],
          ),
          child: Column(
            children: [
              GestureDetector(
                onPanStart: _handlePanStart,
                onPanUpdate: _handlePanUpdate,
                onPanEnd: (_) => _snapToNearestEdge(),
                onPanCancel: _snapToNearestEdge,
                child: Container(
                  height: 82,
                  padding: const EdgeInsets.fromLTRB(16, 12, 10, 12),
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      colors: [Color(0xFF141A24), Color(0xFF10151E)],
                    ),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 46,
                        height: 46,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: RadialGradient(colors: _colors(state)),
                          border: Border.all(
                              color: _stateColor(state, conn), width: 2),
                        ),
                        child: Icon(_stateIcon(state),
                            color: Colors.white.withValues(alpha: 0.9),
                            size: 22),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Text(
                              'ZEUS DevOps',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            const SizedBox(height: 5),
                            Row(
                              children: [
                                _StatusDot(color: statusColor, size: 7),
                                const SizedBox(width: 7),
                                Flexible(
                                  child: Text(
                                    '${_connectionLabel(conn)} · ${_stateLabel(state, conn)}',
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      color:
                                          Colors.white.withValues(alpha: 0.62),
                                      fontSize: 12,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                      IconButton(
                        tooltip: 'Voz',
                        onPressed: _startVoice,
                        icon: const Icon(Icons.mic_rounded),
                        color: Colors.white70,
                      ),
                      IconButton(
                        tooltip: 'Minimizar',
                        onPressed: _closeChatPanel,
                        icon: const Icon(Icons.close_rounded),
                        color: Colors.white70,
                      ),
                    ],
                  ),
                ),
              ),
              Expanded(
                child: Container(
                  color: const Color(0xFF0B0F14),
                  child: history.isEmpty
                      ? Center(
                          child: Text(
                            'Sem mensagens',
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.42),
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        )
                      : ListView.separated(
                          controller: _chatScrollController,
                          padding: const EdgeInsets.fromLTRB(14, 16, 14, 16),
                          itemCount: history.length,
                          separatorBuilder: (_, __) =>
                              const SizedBox(height: 10),
                          itemBuilder: (_, index) =>
                              _buildMessageBubble(history[index]),
                        ),
                ),
              ),
              _buildComposer(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMessageBubble(Map<String, dynamic> message) {
    final role = (message['role'] ?? '').toString().toLowerCase();
    final content = (message['content'] ?? '').toString();
    final fromUser = role == 'user';
    final bubbleColor =
        fromUser ? const Color(0xFF0084FF) : const Color(0xFF202631);
    final textColor = fromUser ? Colors.white : const Color(0xFFE6EAF0);

    return Align(
      alignment: fromUser ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 330),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: bubbleColor,
            borderRadius: BorderRadius.only(
              topLeft: const Radius.circular(20),
              topRight: const Radius.circular(20),
              bottomLeft: Radius.circular(fromUser ? 20 : 6),
              bottomRight: Radius.circular(fromUser ? 6 : 20),
            ),
            border: fromUser
                ? null
                : Border.all(color: Colors.white.withValues(alpha: 0.06)),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            child: Text(
              content,
              style: TextStyle(
                color: textColor,
                fontSize: 14,
                height: 1.32,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildComposer() {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 14),
      decoration: BoxDecoration(
        color: const Color(0xFF10151C),
        border: Border(
            top: BorderSide(color: Colors.white.withValues(alpha: 0.07))),
      ),
      child: Row(
        children: [
          IconButton(
            tooltip: 'Visão',
            onPressed: _startVision,
            icon: const Icon(Icons.visibility_rounded),
            color: Colors.white60,
          ),
          Expanded(
            child: Container(
              constraints: const BoxConstraints(minHeight: 42),
              decoration: BoxDecoration(
                color: const Color(0xFF1B212B),
                borderRadius: BorderRadius.circular(22),
                border: Border.all(color: Colors.white.withValues(alpha: 0.07)),
              ),
              child: TextField(
                controller: _chatInputController,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _sendChatMessage(),
                style: const TextStyle(color: Colors.white, fontSize: 14),
                decoration: InputDecoration(
                  hintText: 'Mensagem',
                  hintStyle: TextStyle(
                    color: Colors.white.withValues(alpha: 0.38),
                  ),
                  border: InputBorder.none,
                  isDense: true,
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 15, vertical: 12),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          IconButton.filled(
            tooltip: 'Enviar',
            onPressed: _sendChatMessage,
            icon: const Icon(Icons.send_rounded, size: 20),
            style: IconButton.styleFrom(
              backgroundColor: const Color(0xFF0084FF),
              foregroundColor: Colors.white,
            ),
          ),
        ],
      ),
    );
  }

  void _handlePanStart(DragStartDetails details) {
    _didDrag = false;
    _dragStartPointer = details.globalPosition;
    _dragStartWindow = null;
    _readWindowPosition();
  }

  Future<void> _readWindowPosition() async {
    try {
      _dragStartWindow = await windowManager.getPosition();
    } catch (_) {
      _dragStartWindow = null;
    }
  }

  Future<void> _handlePanUpdate(DragUpdateDetails details) async {
    final startPointer = _dragStartPointer;
    final startWindow = _dragStartWindow;
    if (startPointer == null || startWindow == null) return;

    final delta = details.globalPosition - startPointer;
    if (delta.distance > _dragThreshold) _didDrag = true;

    try {
      final size = await windowManager.getSize();
      final target = _clampWindowPosition(startWindow + delta, size);
      await windowManager.setPosition(target);
    } catch (_) {
      // Plugin calls are unavailable in widget tests.
    }
  }

  Future<void> _restorePosition() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final size = await windowManager.getSize();
      final savedX = prefs.getDouble(_positionXKey);
      final savedY = prefs.getDouble(_positionYKey);

      if (savedX != null && savedY != null) {
        await windowManager.setPosition(
          _clampWindowPosition(Offset(savedX, savedY), size),
        );
        return;
      }

      await _snapToNearestEdge(preferRight: true, centerVertically: true);
    } catch (_) {
      // Position restore is best effort on unsupported platforms/tests.
    }
  }

  Future<void> _snapToNearestEdge({
    bool preferRight = false,
    bool centerVertically = false,
  }) async {
    try {
      final current = await windowManager.getPosition();
      final windowSize = await windowManager.getSize();
      final screenSize = _screenSize();
      final currentCenterX = current.dx + windowSize.width / 2;
      final snapRight = preferRight || currentCenterX >= screenSize.width / 2;
      final targetX = snapRight
          ? screenSize.width - windowSize.width - _edgeMargin
          : _edgeMargin;
      final targetY = centerVertically
          ? (screenSize.height - windowSize.height) / 2
          : current.dy;
      final target = _clampWindowPosition(Offset(targetX, targetY), windowSize);

      await windowManager.setPosition(target);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setDouble(_positionXKey, target.dx);
      await prefs.setDouble(_positionYKey, target.dy);
    } catch (_) {
      // Snapping should never block the bubble actions.
    } finally {
      _dragStartPointer = null;
      _dragStartWindow = null;
    }
  }

  Offset _clampWindowPosition(Offset position, Size windowSize) {
    final screenSize = _screenSize();
    final maxX = (screenSize.width - windowSize.width - _edgeMargin)
        .clamp(_edgeMargin, double.infinity);
    final maxY = (screenSize.height - windowSize.height - _edgeMargin)
        .clamp(_edgeMargin, double.infinity);

    return Offset(
      position.dx.clamp(_edgeMargin, maxX).toDouble(),
      position.dy.clamp(_edgeMargin, maxY).toDouble(),
    );
  }

  Size _screenSize() {
    final views = WidgetsBinding.instance.platformDispatcher.views;
    if (views.isNotEmpty) {
      final view = views.first;
      final size = view.physicalSize / view.devicePixelRatio;
      if (size.width > 0 && size.height > 0) return size;
    }

    return const Size(1366, 768);
  }

  Future<void> _openChatPanel() async {
    setState(() => _chatOpen = true);
    try {
      await windowManager.setSize(_chatWindowSize);
      await _snapToNearestEdge();
    } catch (_) {
      // Window resizing is unavailable in widget tests.
    }
  }

  Future<void> _closeChatPanel() async {
    setState(() => _chatOpen = false);
    try {
      await windowManager.setSize(_bubbleWindowSize);
      await _snapToNearestEdge();
    } catch (_) {
      // Window resizing is unavailable in widget tests.
    }
  }

  Future<void> _sendChatMessage() async {
    final text = _chatInputController.text.trim();
    if (text.isEmpty) return;
    _chatInputController.clear();
    await ref.read(bubbleStateProvider.notifier).sendText(text);
    await Future<void>.delayed(const Duration(milliseconds: 80));
    if (_chatScrollController.hasClients) {
      await _chatScrollController.animateTo(
        _chatScrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOutCubic,
      );
    }
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

  String _connectionLabel(ZeusConnectionState c) {
    return c == ZeusConnectionState.connected
        ? 'Online'
        : c == ZeusConnectionState.connecting
            ? 'Conectando'
            : 'Offline';
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

class _StatusDot extends StatelessWidget {
  const _StatusDot({required this.color, this.size = 8});

  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color,
        boxShadow: [
          BoxShadow(color: color.withValues(alpha: 0.7), blurRadius: size),
        ],
      ),
    );
  }
}

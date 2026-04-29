import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/zeus_provider.dart';
import '../../domain/models.dart';
import 'dart:math' as math;

class VoiceConversationScreen extends ConsumerStatefulWidget {
  const VoiceConversationScreen({super.key});

  @override
  ConsumerState<VoiceConversationScreen> createState() => _VoiceConversationScreenState();
}

class _VoiceConversationScreenState extends ConsumerState<VoiceConversationScreen> with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 4),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(zeusProvider);
    final isListening = state.isListening;
    final isThinking = state.isThinking;
    final isSpeaking = state.streamingText.isNotEmpty || state.chatHistory.isNotEmpty && state.chatHistory.last.type == MessageType.ai && !isThinking;

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.close, color: Colors.white54),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: const Text("CONVERSATION_MODE", style: TextStyle(fontSize: 10, letterSpacing: 2, color: Colors.white38)),
        centerTitle: true,
      ),
      body: Column(
        children: [
          const Spacer(),
          // Central Pulsating Orb (ChatGPT style)
          Center(
            child: AnimatedBuilder(
              animation: _controller,
              builder: (context, child) {
                return CustomPaint(
                  painter: OrbPainter(
                    progress: _controller.value,
                    isListening: isListening,
                    isThinking: isThinking,
                  ),
                  size: const Size(200, 200),
                );
              },
            ),
          ),
          const SizedBox(height: 50),
          // Transcription Text
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 40),
            child: Column(
              children: [
                if (state.partialSpeech.isNotEmpty)
                  Text(
                    state.partialSpeech,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Color(0xFF00FF41), fontSize: 18, fontWeight: FontWeight.w300),
                  )
                else if (state.streamingText.isNotEmpty)
                  Text(
                    state.streamingText,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white, fontSize: 16, height: 1.5),
                  )
                else
                  Text(
                    isThinking ? "ZEUS_IS_THINKING..." : (isListening ? "LISTENING..." : "TAP_TO_START"),
                    style: const TextStyle(color: Colors.white24, letterSpacing: 2, fontSize: 12),
                  ),
              ],
            ),
          ),
          const Spacer(),
          // Action Button
          Padding(
            padding: const EdgeInsets.only(bottom: 60),
            child: GestureDetector(
              onTap: () => ref.read(zeusProvider.notifier).toggleListening(),
              child: Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isListening ? Colors.red.withOpacity(0.1) : Colors.white.withOpacity(0.05),
                  border: Border.all(
                    color: isListening ? Colors.red : const Color(0xFF00FF41),
                    width: 1,
                  ),
                ),
                child: Icon(
                  isListening ? Icons.stop_rounded : Icons.mic_rounded,
                  color: isListening ? Colors.red : const Color(0xFF00FF41),
                  size: 32,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class OrbPainter extends CustomPainter {
  final double progress;
  final bool isListening;
  final bool isThinking;

  OrbPainter({required this.progress, required this.isListening, required this.isThinking});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final paint = Paint()
      ..style = PaintingStyle.fill;

    // Base Color
    Color baseColor = const Color(0xFF00FF41);
    if (isListening) baseColor = const Color(0xFF00FF41);
    if (isThinking) baseColor = const Color(0xFF00F0FF);

    // Draw Multiple Layers of pulsating circles
    for (int i = 0; i < 4; i++) {
      final double localProgress = (progress + (i * 0.25)) % 1.0;
      final double radius = (size.width / 4) + (localProgress * size.width / 4);
      final double opacity = (1.0 - localProgress) * 0.3;
      
      paint.color = baseColor.withOpacity(opacity);
      canvas.drawCircle(center, radius, paint);
    }

    // Core Orb
    paint.color = baseColor.withOpacity(0.8);
    final double corePulse = 1.0 + 0.1 * math.sin(progress * 2 * math.pi);
    canvas.drawCircle(center, size.width / 6 * corePulse, paint);
    
    // Add glowing effect
    paint.maskFilter = const MaskFilter.blur(BlurStyle.normal, 15);
    paint.color = baseColor.withOpacity(0.2);
    canvas.drawCircle(center, size.width / 4, paint);
  }

  @override
  bool shouldRepaint(covariant OrbPainter oldDelegate) => true;
}

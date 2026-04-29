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
      duration: const Duration(seconds: 10),
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
    
    // UI mapping
    final Color accentColor = isThinking ? const Color(0xFF00F0FF) : const Color(0xFF00FF41);

    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          // Background Glow
          Positioned.fill(
            child: Container(
              decoration: BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment.center,
                  radius: 1.2,
                  colors: [
                    accentColor.withOpacity(0.05),
                    Colors.black,
                  ],
                ),
              ),
            ),
          ),
          
          // Neural Singularity
          Center(
            child: AnimatedBuilder(
              animation: _controller,
              builder: (context, child) {
                return CustomPaint(
                  painter: NeuralSingularityPainter(
                    progress: _controller.value,
                    isListening: isListening,
                    isThinking: isThinking,
                    color: accentColor,
                  ),
                  size: Size(MediaQuery.of(context).size.width * 0.8, MediaQuery.of(context).size.width * 0.8),
                );
              },
            ),
          ),

          // Status & Text
          Positioned(
            bottom: 160,
            left: 0,
            right: 0,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40),
              child: Column(
                children: [
                  Text(
                    isThinking ? "PROCESSANDO..." : (isListening ? "OUVINDO..." : "AGUARDANDO"),
                    style: TextStyle(
                      color: accentColor.withOpacity(0.4),
                      letterSpacing: 4,
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 20),
                  if (state.partialSpeech.isNotEmpty)
                    Text(
                      state.partialSpeech.toUpperCase(),
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w300, letterSpacing: 1),
                    )
                  else if (state.streamingText.isNotEmpty)
                    Text(
                      state.streamingText,
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Colors.white70, fontSize: 14, height: 1.6),
                    ),
                ],
              ),
            ),
          ),

          // Immersive Action Button (Invisible but large)
          Positioned.fill(
            child: GestureDetector(
              onTap: () => ref.read(zeusProvider.notifier).toggleListening(),
              behavior: HitTestBehavior.opaque,
            ),
          ),
          
          // Subtle HUD Decoration
          Positioned(
            top: 60,
            left: 0,
            right: 0,
            child: Center(
              child: Opacity(
                opacity: 0.3,
                child: Column(
                  children: [
                    const Text("ZEUS_COGNITIVE_INTERFACE", style: TextStyle(fontSize: 8, letterSpacing: 5)),
                    const SizedBox(height: 5),
                    Container(width: 40, height: 1, color: accentColor),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class NeuralSingularityPainter extends CustomPainter {
  final double progress;
  final bool isListening;
  final bool isThinking;
  final Color color;

  NeuralSingularityPainter({
    required this.progress, 
    required this.isListening, 
    required this.isThinking,
    required this.color,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final paint = Paint()..style = PaintingStyle.stroke;
    
    // 1. Orbital Rings
    for (int i = 0; i < 3; i++) {
      final double rot = progress * 2 * math.pi + (i * math.pi / 1.5);
      final double radius = (size.width / 3) + math.sin(progress * 4 * math.pi + i) * 5;
      
      paint.strokeWidth = 1.0;
      paint.color = color.withOpacity(0.2);
      canvas.drawCircle(center, radius, paint);
      
      // Ring Dots
      final dotPaint = Paint()..color = color.withOpacity(0.6)..style = PaintingStyle.fill;
      final dotX = center.dx + radius * math.cos(rot);
      final dotY = center.dy + radius * math.sin(rot);
      canvas.drawCircle(Offset(dotX, dotY), 2, dotPaint);
    }

    // 2. Neural Dust (Particles)
    final random = math.Random(42); // Seed for consistency
    for (int i = 0; i < 20; i++) {
      final double dist = (size.width / 4) + random.nextDouble() * (size.width / 3);
      final double angle = random.nextDouble() * 2 * math.pi + (progress * (random.nextBool() ? 1 : -1) * 0.5);
      final double pX = center.dx + dist * math.cos(angle);
      final double pY = center.dy + dist * math.sin(angle);
      final double sizeP = random.nextDouble() * 2;
      
      canvas.drawCircle(Offset(pX, pY), sizeP, Paint()..color = color.withOpacity(0.3));
    }

    // 3. Central Core
    final corePaint = Paint()
      ..style = PaintingStyle.fill
      ..maskFilter = MaskFilter.blur(BlurStyle.normal, isListening ? 20 : 10);
    
    final double pulse = 1.0 + (isListening ? 0.15 : 0.05) * math.sin(progress * 8 * math.pi);
    
    // Core Glow
    corePaint.color = color.withOpacity(0.15);
    canvas.drawCircle(center, (size.width / 5) * pulse, corePaint);
    
    // Core Solid
    final solidPaint = Paint()..color = color.withOpacity(0.8)..style = PaintingStyle.fill;
    canvas.drawCircle(center, (size.width / 8) * pulse, solidPaint);
    
    // Inner Detail
    final detailPaint = Paint()..color = Colors.white.withOpacity(0.5)..style = PaintingStyle.stroke..strokeWidth = 0.5;
    canvas.drawCircle(center, (size.width / 10) * pulse, detailPaint);
  }

  @override
  bool shouldRepaint(covariant NeuralSingularityPainter oldDelegate) => true;
}

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/zeus_provider.dart';
import 'chat_screen.dart';
import 'voice_conversation_screen.dart';
import 'remote_control_screen.dart';
import 'dart:math' as math;

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> with SingleTickerProviderStateMixin {
  late AnimationController _neuralController;

  @override
  void initState() {
    super.initState();
    _neuralController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 10),
    )..repeat();
  }

  @override
  void dispose() {
    _neuralController.dispose();
    super.dispose();
  }

  Color _moodColor(String mood) {
    switch (mood.toUpperCase()) {
      case 'CODING':
        return const Color(0xFF8C3CFF);
      case 'THINKING':
        return const Color(0xFF00F0FF);
      case 'SURGE':
        return Colors.redAccent;
      case 'ADAPTIVE':
        return const Color(0xFF00FF41);
      default:
        return const Color(0xFF00FF41);
    }
  }

  @override
  Widget build(BuildContext context) {
    final zeus = ref.watch(zeusProvider);
    final status = zeus.status;
    final cpu = status?.cpu ?? 0;
    final ram = status?.ram ?? 0;
    final mood = status?.mood ?? 'IDLE';
    final events = status?.activeTasks ?? 0;
    final moodColor = _moodColor(mood);

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        elevation: 0,
        title: const Text('ZEUS_GEMINI_3_HUD', style: TextStyle(letterSpacing: 4, fontWeight: FontWeight.bold, color: Color(0xFF00FF41))),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.power_settings_new, color: Colors.white24),
            onPressed: () {
              ref.read(zeusProvider.notifier).logout();
              Navigator.of(context).popUntil((route) => route.isFirst);
            },
          ),
        ],
      ),
      body: Stack(
        children: [
          // Background Matrix Rain Simulation
          Positioned.fill(
            child: AnimatedBuilder(
              animation: _neuralController,
              builder: (context, child) {
                return CustomPaint(
                  painter: MatrixBackgroundPainter(
                    progress: _neuralController.value,
                    color: const Color(0xFF00FF41).withOpacity(0.05),
                  ),
                );
              },
            ),
          ),
          
          Padding(
            padding: const EdgeInsets.all(20.0),
            child: Column(
              children: [
                _buildSystemHeader(zeus.isConnected, moodColor),
                const SizedBox(height: 25),
                _buildMetricCard("CPU_LOAD", "${cpu.toStringAsFixed(1)}%", Icons.dns, const Color(0xFF00FF41), cpu / 100),
                const SizedBox(height: 15),
                _buildMetricCard("MEM_USAGE", "${ram.toStringAsFixed(1)}%", Icons.memory, const Color(0xFF00F0FF), ram / 100),
                const SizedBox(height: 15),
                _buildMetricCard("COG_MOOD", mood, Icons.psychology, moodColor, null),
                const SizedBox(height: 15),
                _buildMetricCard("EVT_COUNT", "$events", Icons.grid_view, Colors.white70, null),
                const Spacer(),
                
                _buildActionButton(
                  "NEURAL_CHAT", 
                  Icons.chat_bubble_outline, 
                  const Color(0xFF00FF41), 
                  () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ChatScreen()))
                ),
                const SizedBox(height: 15),
                _buildActionButton(
                  "VOICE_CONVERSATION", 
                  Icons.graphic_eq, 
                  const Color(0xFF00F0FF), 
                  () => Navigator.push(context, MaterialPageRoute(builder: (_) => const VoiceConversationScreen())),
                  isPrimary: true
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSystemHeader(bool connected, Color moodColor) {
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: const Color(0xFF0D0D0D),
        border: Border.all(color: connected ? const Color(0xFF00FF41) : Colors.red, width: 0.5),
        borderRadius: BorderRadius.circular(5),
      ),
      child: Row(
        children: [
          _buildStatusPulse(connected),
          const SizedBox(width: 15),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                connected ? "SYSTEM_ONLINE" : "SYSTEM_OFFLINE",
                style: TextStyle(
                  color: connected ? const Color(0xFF00FF41) : Colors.red,
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1
                ),
              ),
              const Text("ENCRYPTION: AES-256-GCM", style: TextStyle(color: Colors.white24, fontSize: 10)),
            ],
          ),
          const Spacer(),
          Text("v1.0.4-LTS", style: TextStyle(color: moodColor.withOpacity(0.5), fontSize: 10)),
        ],
      ),
    );
  }

  Widget _buildStatusPulse(bool online) {
    return Container(
      width: 12,
      height: 12,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: online ? const Color(0xFF00FF41) : Colors.red,
        boxShadow: [
          BoxShadow(
            color: (online ? const Color(0xFF00FF41) : Colors.red).withOpacity(0.5),
            blurRadius: 10,
            spreadRadius: 2
          )
        ],
      ),
    );
  }

  Widget _buildMetricCard(String title, String value, IconData icon, Color color, double? progress) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFF0D0D0D),
        borderRadius: BorderRadius.circular(5),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(width: 20),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontSize: 10, color: Colors.white38, letterSpacing: 2)),
                const SizedBox(height: 5),
                Text(value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: color)),
                if (progress != null) ...[
                  const SizedBox(height: 10),
                  LinearProgressIndicator(
                    value: progress.clamp(0.0, 1.0),
                    backgroundColor: Colors.white10,
                    valueColor: AlwaysStoppedAnimation(color),
                    minHeight: 1,
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionButton(String label, IconData icon, Color color, VoidCallback onPressed, {bool isPrimary = false}) {
    return InkWell(
      onTap: onPressed,
      child: Container(
        height: 60,
        decoration: BoxDecoration(
          color: isPrimary ? color.withOpacity(0.1) : Colors.black,
          border: Border.all(color: color, width: 1),
          borderRadius: BorderRadius.circular(5),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, color: color, size: 20),
            const SizedBox(width: 15),
            Text(
              label,
              style: TextStyle(color: color, fontSize: 14, fontWeight: FontWeight.bold, letterSpacing: 2),
            ),
          ],
        ),
      ),
    );
  }
}

class MatrixBackgroundPainter extends CustomPainter {
  final double progress;
  final Color color;

  MatrixBackgroundPainter({required this.progress, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1.0;

    final random = math.Random(42);
    final columns = (size.width / 20).floor();
    
    for (var i = 0; i < columns; i++) {
      final x = i * 20.0;
      final speed = 0.5 + random.nextDouble();
      final y = (progress * size.height * speed + (random.nextDouble() * size.height)) % size.height;
      
      canvas.drawCircle(Offset(x, y), 1.0, paint);
      canvas.drawCircle(Offset(x, (y - 40) % size.height), 0.5, Paint()..color = color.withOpacity(0.2));
      canvas.drawCircle(Offset(x, (y - 80) % size.height), 0.3, Paint()..color = color.withOpacity(0.1));
    }
  }

  @override
  bool shouldRepaint(covariant MatrixBackgroundPainter oldDelegate) => true;
}

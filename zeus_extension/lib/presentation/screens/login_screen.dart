import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/zeus_provider.dart';
import 'dashboard_screen.dart';
import 'package:google_fonts/google_fonts.dart';
import 'dart:math' as math;

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final TextEditingController _urlController = TextEditingController(text: "http://192.168.1.5:8080");
  final TextEditingController _tokenController = TextEditingController();
  final TextEditingController _lanTokenController = TextEditingController();
  bool _isLoading = false;

  void _doLogin() async {
    setState(() => _isLoading = true);
    final success = await ref.read(zeusProvider.notifier).login(
      _urlController.text.trim(),
      _tokenController.text.trim(),
      lanToken: _lanTokenController.text.trim().isEmpty ? null : _lanTokenController.text.trim(),
    );
    if (!mounted) return;
    setState(() => _isLoading = false);

    if (success) {
      Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const DashboardScreen()));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: Colors.red,
          content: Text("CONNECTION_FAILED: ACCESS_DENIED", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        ),
      );
    }
  }

  @override
  void dispose() {
    _urlController.dispose();
    _tokenController.dispose();
    _lanTokenController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: Stack(
        children: [
          _buildMatrixBackground(),
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(40),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const SizedBox(height: 60),
                  _buildLogo(),
                  const SizedBox(height: 50),
                  _buildTextField(_urlController, "SECURE_HOST_URL", Icons.dns),
                  const SizedBox(height: 20),
                  _buildTextField(_tokenController, "JWT_IDENTITY_TOKEN", Icons.vpn_key, obscure: true),
                  const SizedBox(height: 20),
                  _buildTextField(_lanTokenController, "ENCRYPTION_KEY_LAN", Icons.shield, obscure: true),
                  const SizedBox(height: 50),
                  _buildConnectButton(),
                  const SizedBox(height: 30),
                  const Text(
                    "ZEUS_MOBILE_EXTENSION v1.0.4\nENCRYPTED NEURAL LINK",
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Colors.white24, fontSize: 10, letterSpacing: 2),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLogo() {
    return Column(
      children: [
        const Icon(Icons.psychology, size: 100, color: Color(0xFF00FF41)),
        const SizedBox(height: 10),
        Text(
          "ZEUS_CORE",
          style: GoogleFonts.shareTechMono(
            fontSize: 32,
            fontWeight: FontWeight.bold,
            color: const Color(0xFF00FF41),
            letterSpacing: 8,
          ),
        ),
      ],
    );
  }

  Widget _buildTextField(TextEditingController controller, String label, IconData icon, {bool obscure = false}) {
    return TextField(
      controller: controller,
      obscureText: obscure,
      style: const TextStyle(color: Color(0xFF00FF41)),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: Colors.white38, fontSize: 12),
        prefixIcon: Icon(icon, color: const Color(0xFF00FF41), size: 20),
        enabledBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: Colors.white12),
        ),
        focusedBorder: const OutlineInputBorder(
          borderSide: BorderSide(color: Color(0xFF00FF41)),
        ),
      ),
    );
  }

  Widget _buildConnectButton() {
    return InkWell(
      onTap: _isLoading ? null : _doLogin,
      child: Container(
        height: 60,
        width: double.infinity,
        decoration: BoxDecoration(
          color: _isLoading ? Colors.white10 : const Color(0xFF00FF41).withOpacity(0.1),
          border: Border.all(color: const Color(0xFF00FF41)),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Center(
          child: _isLoading 
            ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF00FF41)))
            : const Text(
                "INITIALIZE_NEURAL_LINK",
                style: TextStyle(color: Color(0xFF00FF41), fontWeight: FontWeight.bold, letterSpacing: 2),
              ),
        ),
      ),
    );
  }

  Widget _buildMatrixBackground() {
    return Positioned.fill(
      child: Opacity(
        opacity: 0.05,
        child: CustomPaint(
          painter: MatrixPainter(),
        ),
      ),
    );
  }
}

class MatrixPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = const Color(0xFF00FF41);
    final random = math.Random(42);
    for (var i = 0; i < 50; i++) {
      canvas.drawCircle(
        Offset(random.nextDouble() * size.width, random.nextDouble() * size.height),
        1,
        paint,
      );
    }
  }
  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

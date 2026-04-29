import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'presentation/screens/login_screen.dart';

void main() {
  runApp(const ProviderScope(child: ZeusApp()));
}

class ZeusApp extends StatelessWidget {
  const ZeusApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ZEUS Extension',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        primaryColor: const Color(0xFF00FF41), // Matrix Green
        scaffoldBackgroundColor: Colors.black,
        textTheme: GoogleFonts.shareTechMonoTextTheme(ThemeData.dark().textTheme).apply(
          bodyColor: const Color(0xFF00FF41),
          displayColor: const Color(0xFF00FF41),
        ),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF00FF41),
          secondary: Color(0xFF00F0FF),
          surface: Color(0xFF0D0D0D),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.black,
          elevation: 0,
          titleTextStyle: TextStyle(
            color: Color(0xFF00FF41),
            fontSize: 20,
            fontWeight: FontWeight.bold,
            letterSpacing: 2,
          ),
        ),
      ),
      home: const LoginScreen(),
    );
  }
}

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_acrylic/flutter_acrylic.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hotkey_manager/hotkey_manager.dart';
import 'package:window_manager/window_manager.dart';

import 'presentation/overlay/zeus_bubble_app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await hotKeyManager.unregisterAll();

  if (Platform.isLinux || Platform.isWindows || Platform.isMacOS) {
    await Window.initialize();
    await Window.setEffect(effect: WindowEffect.transparent);
    await windowManager.ensureInitialized();
    const options = WindowOptions(
      size: Size(108, 108),
      center: true,
      backgroundColor: Colors.transparent,
      skipTaskbar: false,
      titleBarStyle: TitleBarStyle.hidden,
      alwaysOnTop: true,
    );

    await windowManager.waitUntilReadyToShow(options, () async {
      await windowManager.setAsFrameless();
      await windowManager.setAlwaysOnTop(true);
      await windowManager.setResizable(false);
      await windowManager.show();
      await windowManager.focus();
    });
  }

  runApp(const ProviderScope(child: ZeusBubbleApp()));
}

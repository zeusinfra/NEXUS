// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:zeus_extension/presentation/overlay/zeus_bubble_app.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('Boots ZEUS bubble overlay', (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: ZeusBubbleApp()));
    await tester.pump();

    expect(find.byType(ZeusBubbleApp), findsOneWidget);
  });
}

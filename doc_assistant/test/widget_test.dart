import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:doc_assistant/app.dart';

void main() {
  testWidgets('App smoke test - loads login page', (WidgetTester tester) async {
    // Build the app
    await tester.pumpWidget(const DocAssistantApp());

    // Look for Login form elements
    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(2)); // email + password
    expect(find.text('Sign in'), findsOneWidget);

    // Try entering some text
    await tester.enterText(find.byType(TextField).first, 'me@example.com');
    await tester.enterText(find.byType(TextField).last, 'password123');
    await tester.tap(find.text('Sign in'));
    await tester.pump();

    // Because login is stubbed to always succeed, user should be redirected
    // to the Docs list (with an AppBar titled "Your Documents")
    expect(find.text('Your Documents'), findsOneWidget);
  });
}

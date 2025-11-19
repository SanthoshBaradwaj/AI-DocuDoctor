import 'package:flutter/material.dart';
import 'routing/app_router.dart';

class DocAssistantApp extends StatelessWidget {
  const DocAssistantApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Doc Assistant',
      theme: ThemeData(colorSchemeSeed: Colors.blue, useMaterial3: true),
      routerConfig: appRouter,
    );
  }
}

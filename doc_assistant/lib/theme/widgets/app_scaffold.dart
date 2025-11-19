import 'package:flutter/material.dart';

class AppScaffold extends StatelessWidget {
  final String title;
  final Widget body;
  final List<Widget>? actions;
  final Widget? floatingActionButton;

  const AppScaffold({
    super.key,
    required this.title,
    required this.body,
    this.actions,
    this.floatingActionButton,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF1E1B4B), Color(0xFF312E81), Color(0xFF6D28D9)],
        ),
      ),
      child: Scaffold(
        // ✅ let Scaffold resize when keyboard appears
        resizeToAvoidBottomInset: true,
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          title: Text(title),
          backgroundColor: Colors.transparent,
          actions: actions,
        ),
        // ✅ SafeArea keeps content off notches; padding handled by pages
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: body,
          ),
        ),
        floatingActionButton: floatingActionButton,
      ),
    );
  }
}

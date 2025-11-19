import 'package:flutter/material.dart';

/// A simple, consistent scaffold with optional actions
class AppScaffold extends StatelessWidget {
  final String title;
  final Widget body;
  final List<Widget>? actions;
  final Widget? floatingActionButton;
  final PreferredSizeWidget? bottom;
  final bool centerTitle;

  const AppScaffold({
    super.key,
    required this.title,
    required this.body,
    this.actions,
    this.floatingActionButton,
    this.bottom,
    this.centerTitle = false,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: actions,
        bottom: bottom,
        centerTitle: centerTitle,
      ),
      floatingActionButton: floatingActionButton,
      body: SafeArea(child: body),
    );
  }
}

/// A primary filled button with full-width convenience.
class PrimaryButton extends StatelessWidget {
  final VoidCallback? onPressed;
  final String label;
  final IconData? icon;
  final bool loading;

  const PrimaryButton({
    super.key,
    required this.onPressed,
    required this.label,
    this.icon,
    this.loading = false,
  });

  @override
  Widget build(BuildContext context) {
    final child = loading ? Text('$label…') : Text(label);
    return SizedBox(
      width: double.infinity,
      child: icon == null
          ? FilledButton(onPressed: loading ? null : onPressed, child: child)
          : FilledButton.icon(
              onPressed: loading ? null : onPressed,
              icon: Icon(icon),
              label: child,
            ),
    );
  }
}

/// A small outlined button, handy for secondary actions.
class SecondaryButton extends StatelessWidget {
  final VoidCallback? onPressed;
  final String label;

  const SecondaryButton({super.key, required this.onPressed, required this.label});

  @override
  Widget build(BuildContext context) {
    return OutlinedButton(onPressed: onPressed, child: Text(label));
  }
}

/// Consistent text field with label and optional prefix icon.
class LabeledTextField extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final IconData? icon;
  final bool obscure;
  final TextInputType? keyboardType;
  final void Function(String)? onSubmitted;

  const LabeledTextField({
    super.key,
    required this.controller,
    required this.label,
    this.icon,
    this.obscure = false,
    this.keyboardType,
    this.onSubmitted,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      obscureText: obscure,
      keyboardType: keyboardType,
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: icon == null ? null : Icon(icon),
      ),
      onSubmitted: onSubmitted,
    );
  }
}

/// Inline error/info banner.
class MessageBanner extends StatelessWidget {
  final String message;
  final Color? color;
  final IconData? icon;

  const MessageBanner.error(this.message, {super.key})
      : color = const Color(0xFFFFE6E6),
        icon = Icons.error_outline;

  const MessageBanner.info(this.message, {super.key})
      : color = const Color(0xFFE7F1FF),
        icon = Icons.info_outline;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: Colors.black12),
      ),
      child: Row(
        children: [
          Icon(icon, size: 18),
          const SizedBox(width: 8),
          Expanded(child: Text(message)),
        ],
      ),
    );
  }
}

/// Simple centered placeholder when lists are empty.
class EmptyPlaceholder extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;

  const EmptyPlaceholder({
    super.key,
    required this.title,
    required this.subtitle,
    this.icon = Icons.inbox_outlined,
  });

  @override
  Widget build(BuildContext context) {
    final th = Theme.of(context);
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 42, color: th.colorScheme.primary),
            const SizedBox(height: 12),
            Text(title, style: th.textTheme.titleMedium),
            const SizedBox(height: 6),
            Text(subtitle, textAlign: TextAlign.center, style: th.textTheme.bodyMedium),
          ],
        ),
      ),
    );
  }
}

/// Linear progress with label.
class LabeledProgressBar extends StatelessWidget {
  final double? value; // 0..1 or null for indeterminate
  final String? label;

  const LabeledProgressBar({super.key, this.value, this.label});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        LinearProgressIndicator(value: value),
        if (label != null) ...[
          const SizedBox(height: 6),
          Text(label!, textAlign: TextAlign.center),
        ],
      ],
    );
  }
}

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../theme/widgets/app_scaffold.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int idx = 0;

  static const _pages = [
    ('Documents', Icons.description, '/docs'),
    ('Upload', Icons.upload_file, '/upload'),
    ('Chat', Icons.chat_bubble, '/chat'),
    ('Settings', Icons.settings, '/settings'),
  ];

  @override
  Widget build(BuildContext context) {
    return AppScaffold(
      title: 'Home',
      body: Column(
        children: [
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: List.generate(_pages.length, (i) {
              final (label, icon, route) = _pages[i];
              final selected = i == idx;
              return ChoiceChip(
                labelPadding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                avatar: Icon(icon,
                    color: selected ? Colors.white : Colors.white70, size: 18),
                label: Text(label),
                selected: selected,
                onSelected: (_) {
                  setState(() => idx = i);
                  context.go(route);
                },
              );
            }),
          ),
          const SizedBox(height: 16),
          const Expanded(
            child: Center(
              child: Text(
                'Pick a tab to navigate.',
                style: TextStyle(color: Colors.white70),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

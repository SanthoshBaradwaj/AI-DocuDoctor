import 'package:flutter/material.dart';
import '../../../theme/widgets/app_card.dart';
import '../data/document.dart';

class DocumentCard extends StatelessWidget {
  final Document doc;
  final VoidCallback onOpen;
  final VoidCallback? onAnalyze;
  const DocumentCard({super.key, required this.doc, required this.onOpen, this.onAnalyze});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      leading: const CircleAvatar(child: Icon(Icons.description)),
      title: doc.title,
      subtitle: doc.excerpt,
      onTap: onOpen,
      trailing: [
        IconButton(
          tooltip: 'Analyze',
          onPressed: onAnalyze,
          icon: const Icon(Icons.analytics_outlined),
        ),
        const Icon(Icons.chevron_right),
      ],
    );
  }
}

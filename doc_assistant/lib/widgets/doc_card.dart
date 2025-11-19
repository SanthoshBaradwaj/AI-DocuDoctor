import 'package:flutter/material.dart';
import '../models/doc.dart';

class DocCard extends StatelessWidget {
  final Doc doc;
  final VoidCallback? onTap;
  const DocCard({super.key, required this.doc, this.onTap});

  @override
  Widget build(BuildContext context) {
    final statusColor = switch (doc.status) {
      'ready' => Colors.green,
      'processing' => Colors.orange,
      _ => Colors.grey,
    };
    return Card(
      elevation: 1,
      child: ListTile(
        onTap: onTap,
        title: Text(doc.title, maxLines: 1, overflow: TextOverflow.ellipsis),
        subtitle: Text(doc.excerpt, maxLines: 2, overflow: TextOverflow.ellipsis),
        trailing: Chip(
          label: Text(doc.status),
          backgroundColor: statusColor.withOpacity(.15),
          labelStyle: TextStyle(color: statusColor),
          side: BorderSide(color: statusColor.withOpacity(.4)),
        ),
      ),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../app/providers.dart';
import '../data/graph_repository.dart';
import '../domain/models.dart';

IconData kindIcon(RecordKind k) => switch (k) {
      RecordKind.ticket => Icons.confirmation_number_outlined,
      RecordKind.document => Icons.description_outlined,
      _ => Icons.memory,
    };

/// What the knowledge index finds about the same thing as this record — the semantic graph, as a list. Read
/// when opened: it asks the index, which is not free.
class RelatedByMeaning extends StatefulWidget {
  const RelatedByMeaning({super.key, required this.kind, required this.uid, this.initiallyOpen = false});

  final RecordKind kind;
  final String uid;
  final bool initiallyOpen;

  @override
  State<RelatedByMeaning> createState() => _RelatedByMeaningState();
}

class _RelatedByMeaningState extends State<RelatedByMeaning> {
  late bool _open = widget.initiallyOpen;

  @override
  Widget build(BuildContext context) => ExpansionTile(
        key: const Key('related-by-meaning'),
        initiallyExpanded: widget.initiallyOpen,
        leading: const Icon(Icons.auto_awesome_outlined),
        title: const Text('Related by meaning'),
        subtitle: const Text('What the written knowledge says is about the same thing'),
        onExpansionChanged: (v) => setState(() => _open = v),
        children: [if (_open) _Links(kind: widget.kind, uid: widget.uid)],
      );
}

class _Links extends ConsumerWidget {
  const _Links({required this.kind, required this.uid});

  final RecordKind kind;
  final String uid;

  @override
  Widget build(BuildContext context, WidgetRef ref) => ref.watch(byMeaningProvider((kind, uid))).when(
        loading: () => const Padding(padding: EdgeInsets.all(16), child: LinearProgressIndicator()),
        error: (e, _) => ListTile(title: Text('$e')),
        data: (s) {
          if (!s.available) return ListTile(title: Text(s.reason ?? 'The written knowledge is not indexed.'));
          if (s.links.isEmpty) {
            return ListTile(
                title: Text(s.basis == 'nothing indexed'
                    ? 'Nothing of this record is indexed yet.'
                    : 'Nothing else is about the same thing.'));
          }
          return Column(children: [for (final l in s.links) SemanticTile(l)]);
        },
      );
}

/// One record related by meaning: how close, and — on opening — the two passages that make it so.
class SemanticTile extends StatelessWidget {
  const SemanticTile(this.link, {super.key});

  final GraphLink link;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final t = link.target;
    return ExpansionTile(
      key: Key('meaning-${t.uid}'),
      leading: Icon(kindIcon(t.kind)),
      title: Text(t.title ?? t.uid, maxLines: 2, overflow: TextOverflow.ellipsis),
      subtitle: Row(children: [
        SizedBox(
          width: 64,
          child: LinearProgressIndicator(value: link.score ?? 0, color: Colors.teal, minHeight: 5,
              borderRadius: BorderRadius.circular(3)),
        ),
        const SizedBox(width: 8),
        Text((link.score ?? 0).toStringAsFixed(2), style: theme.textTheme.bodySmall),
        if (t.subtitle != null) ...[
          const SizedBox(width: 8),
          Expanded(child: Text(t.subtitle!, maxLines: 1, overflow: TextOverflow.ellipsis, style: theme.textTheme.bodySmall)),
        ],
      ]),
      childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      expandedCrossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (link.excerpt != null) Text('“${link.excerpt}”', style: theme.textTheme.bodySmall),
        if (link.matched != null) ...[
          const SizedBox(height: 6),
          Text('closest to this record’s: “${link.matched}”',
              style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.outline)),
        ],
        Align(
          alignment: Alignment.centerRight,
          child: TextButton(onPressed: () => context.push(t.route), child: const Text('Open')),
        ),
      ],
    );
  }
}

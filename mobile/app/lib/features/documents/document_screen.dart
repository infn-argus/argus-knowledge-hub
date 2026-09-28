import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../widgets/common.dart';

/// A procedure or document. The field must never mistake a draft or an outdated revision for the
/// one to work from, so the state is said before the content (flutter-app-design §5.5).
class DocumentScreen extends ConsumerWidget {
  const DocumentScreen({super.key, required this.uid});

  final String uid;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = ref.watch(documentDetailProvider(uid));
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: Text(r.value?.code ?? 'Document')),
      body: r.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ProblemView(e, onRetry: () => ref.invalidate(documentDetailProvider(uid))),
        data: (d) => ListView(padding: const EdgeInsets.only(bottom: 32), children: [
          if (d.supersededBy != null)
            NoticeBar(
              key: const Key('doc-superseded'),
              icon: Icons.block,
              severe: true,
              text: 'Superseded. Do not work from this document.',
            )
          else if (d.revisionState == null)
            const NoticeBar(icon: Icons.block, severe: true, text: 'No current revision. There is nothing to work from.')
          else if (!d.approved)
            NoticeBar(
                key: const Key('doc-not-approved'),
                icon: Icons.edit_note,
                severe: true,
                text: 'Revision ${d.revisionNumber} is ${d.revisionState}, not approved. Do not work from it.')
          else if (d.outdated)
            NoticeBar(
                key: const Key('doc-overdue'),
                icon: Icons.warning_amber,
                text: 'Periodic review was due on ${formatWhenDate(d.nextReviewDue)}. Check with the owner before relying on it.'),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(d.title, key: const Key('doc-title'), style: theme.textTheme.headlineSmall),
              const SizedBox(height: 8),
              Wrap(spacing: 8, children: [
                StatusChip(d.authorityLevel),
                if (d.revisionNumber != null) StatusChip('rev. ${d.revisionNumber}'),
                if (d.revisionState != null)
                  StatusChip(d.revisionState!, tone: d.approved ? theme.colorScheme.primary : theme.colorScheme.error),
              ]),
              if (d.supersededBy != null) ...[
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: () => context.push('/document/${d.supersededBy}'),
                  icon: const Icon(Icons.arrow_forward),
                  label: const Text('Open the document that replaces it'),
                ),
              ],
            ]),
          ),
          if (d.steps.isNotEmpty) ...[
            const SectionHeader('Steps'),
            for (final (i, s) in d.steps.indexed)
              ListTile(leading: CircleAvatar(radius: 14, child: Text('${i + 1}')), title: Text(s)),
          ],
          if ((d.body ?? '').isNotEmpty) ...[
            const SectionHeader('Content'),
            Padding(padding: const EdgeInsets.symmetric(horizontal: 16), child: SelectableText(d.body!)),
          ],
        ]),
      ),
    );
  }
}

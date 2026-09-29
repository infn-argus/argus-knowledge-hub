import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../core/problem.dart';
import '../../domain/capture.dart';
import '../../widgets/common.dart';

/// The review items routed to this person, one at a time, with their evidence (flutter-app-design
/// §4.2 `review`). Only the decisions the server allows from the field are offered; the rest say
/// to decide on the web, where the full record and the graph are.
class ReviewScreen extends ConsumerStatefulWidget {
  const ReviewScreen({super.key});

  @override
  ConsumerState<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends ConsumerState<ReviewScreen> {
  final _pages = PageController();
  final _done = <String>{};
  bool _busy = false;

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  Future<String?> _ask(String title, String label, {bool required = true}) => showDialog<String>(
        context: context,
        builder: (_) => _TextDialog(title: title, label: label, required: required),
      );

  Future<void> _decide(ReviewItem item, String decision) async {
    String? reason;
    Object? value;
    if (decision == 'reject' || decision == 'resolve' || decision == 'dismissed') {
      reason = await _ask(decision == 'resolve' ? 'What was the difference?' : 'Why?', 'Reason');
      if (reason == null) return;
    }
    if (decision == 'edit') {
      value = await _ask('The correct value', ProposalLabel.of(item));
      if (value == null) return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(reviewRepositoryProvider).decide(item, decision, reason: reason, value: value);
      setState(() => _done.add(item.key));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${item.title}: $decision.')));
      }
    } on Problem catch (p) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(p.message)));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final r = ref.watch(myReviewItemsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Review')),
      body: r.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ProblemView(e, onRetry: () => ref.invalidate(myReviewItemsProvider)),
        data: (all) {
          final items = all.where((i) => !_done.contains(i.key)).toList();
          if (items.isEmpty) return const Center(child: Text('Nothing is waiting for you.'));
          return Column(children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
              child: Row(children: [
                IconButton(
                  key: const Key('review-previous'),
                  tooltip: 'Previous',
                  onPressed: () => _pages.previousPage(duration: const Duration(milliseconds: 200), curve: Curves.easeOut),
                  icon: const Icon(Icons.chevron_left),
                ),
                Expanded(
                  child: Text('${items.length} waiting', key: const Key('review-count'), textAlign: TextAlign.center),
                ),
                IconButton(
                  key: const Key('review-next'),
                  tooltip: 'Next',
                  onPressed: () => _pages.nextPage(duration: const Duration(milliseconds: 200), curve: Curves.easeOut),
                  icon: const Icon(Icons.chevron_right),
                ),
              ]),
            ),
            Expanded(
              child: PageView(
                controller: _pages,
                children: [for (final i in items) _card(i)],
              ),
            ),
          ]);
        },
      ),
    );
  }

  Widget _card(ReviewItem item) {
    final theme = Theme.of(context);
    final d = item.detail;
    final lines = <(String, String)>[];
    switch (item.kind) {
      case 'replacement_proposal':
        final incoming = BriefRecord.fromJson(d['incoming']);
        final current = d['current'] is Map ? BriefRecord.fromJson((d['current'] as Map)['unit']) : null;
        lines.addAll([
          ('Installed now', current?.label ?? 'nothing'),
          ('To install', incoming?.label ?? '?'),
          ('Why it waits', ((d['reasons'] as List?) ?? const []).join('; ')),
          ('Submitted by', '${d['submitted_by'] ?? ''}'),
        ]);
      case 'outgoing_discrepancy':
        lines.addAll([
          ('Recorded', BriefRecord.fromJson(d['recorded'])?.label ?? 'nothing'),
          ('Found in place', BriefRecord.fromJson(d['scanned'])?.label ?? 'not identified'),
          ('Reported by', '${d['submitted_by'] ?? ''}'),
        ]);
      case 'stale_command':
        lines.addAll([
          ('Submitted', '${(d['command'] as Map?)?['changes'] ?? d['command']}'),
          ('Current', '${d['current']}'),
          ('By', '${d['submitted_by'] ?? ''}'),
        ]);
      case 'ai_proposal':
        lines.addAll([
          ('Field', '${d['predicate']}'.replaceFirst('attr:', '')),
          ('Proposed', '${d['value']}'),
          if (d['confidence'] != null) ('Confidence', '${((d['confidence'] as num) * 100).round()}%'),
          if (d['quote'] != null) ('Read in', '“${d['quote']}”'),
        ]);
    }
    final evidence = d['evidence'];
    return ListView(key: Key('review-${item.key}'), padding: const EdgeInsets.all(16), children: [
      Text(item.title, style: theme.textTheme.titleLarge),
      const SizedBox(height: 4),
      Wrap(spacing: 8, children: [
        StatusChip(item.queue.replaceAll('_', ' ')),
        StatusChip('${item.age} working days', tone: item.overdue ? theme.colorScheme.error : null),
      ]),
      if (item.record != null)
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.place_outlined),
          title: Text(item.record!.label),
          subtitle: Text(item.record!.type ?? ''),
          onTap: item.record!.uid == null ? null : () => context.push('/asset/${item.record!.uid}'),
        ),
      for (final (k, v) in lines)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SizedBox(width: 120, child: Text(k, style: theme.textTheme.labelLarge)),
            Expanded(child: SelectableText(v)),
          ]),
        ),
      if (evidence is Map && evidence.isNotEmpty) ...[
        const SizedBox(height: 8),
        Text('Evidence', style: theme.textTheme.labelLarge),
        for (final e in evidence.entries) Text('${e.key}: ${e.value}'),
      ],
      const SizedBox(height: 20),
      if (item.decisions.isEmpty)
        const NoticeBar(icon: Icons.computer, text: 'Decide this on the web, with the full record and the graph.')
      else
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final dec in item.decisions)
            (dec == 'confirm' || dec == 'applied' || dec == 'resolve' ? FilledButton.new : OutlinedButton.new)(
              key: Key('decide-${item.id}-$dec'),
              onPressed: _busy ? null : () => _decide(item, dec),
              child: Text(_label(dec)),
            ),
        ]),
    ]);
  }

  static String _label(String decision) => switch (decision) {
        'confirm' => 'Confirm',
        'reject' => 'Reject',
        'edit' => 'Correct',
        'resolve' => 'Resolved',
        'applied' => 'I redid it',
        'dismissed' => 'Dismiss',
        _ => decision,
      };
}

class ProposalLabel {
  static String of(ReviewItem i) => '${i.detail['predicate'] ?? 'Value'}'.replaceFirst('attr:', '');
}

class _TextDialog extends StatefulWidget {
  const _TextDialog({required this.title, required this.label, this.required = true});

  final String title;
  final String label;
  final bool required;

  @override
  State<_TextDialog> createState() => _TextDialogState();
}

class _TextDialogState extends State<_TextDialog> {
  final _c = TextEditingController();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
        title: Text(widget.title),
        content: TextField(
            key: const Key('review-text'),
            controller: _c,
            autofocus: true,
            onChanged: (_) => setState(() {}),
            decoration: InputDecoration(labelText: widget.label)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(
            key: const Key('review-text-ok'),
            onPressed: widget.required && _c.text.trim().isEmpty ? null : () => Navigator.pop(context, _c.text.trim()),
            child: const Text('OK'),
          ),
        ],
      );
}

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/providers.dart';
import '../../app/queue.dart';
import '../../data/command_queue.dart';
import '../../widgets/common.dart';

/// Changes kept on this device (flutter-app-design §5.2): what is waiting, what was sent, and what
/// needs the person. A refused change is kept until the person discards it, so nothing is silently
/// lost.
class OutboxScreen extends ConsumerWidget {
  const OutboxScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final all = ref.watch(queueProvider).value ?? const <PendingCommand>[];
    final reach = ref.watch(reachabilityProvider);
    final queue = ref.read(queueProvider.notifier);
    final waiting = all.where((c) => c.open).toList();
    final needs = all.where((c) => c.needsPerson).toList();
    final sent = all.where((c) => c.status == CommandStatus.accepted).toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Unsent changes')),
      body: ListView(padding: const EdgeInsets.only(bottom: 32), children: [
        if (!reach.reachable)
          const NoticeBar(icon: Icons.cloud_off, text: 'ARGUS cannot be reached now. Changes are sent when it can.'),
        Padding(
          padding: const EdgeInsets.all(16),
          child: FilledButton.icon(
            key: const Key('outbox-send'),
            onPressed: waiting.isEmpty ? null : () => queue.sync(force: true),
            icon: const Icon(Icons.sync),
            label: Text('Send now (${waiting.length})'),
          ),
        ),
        if (needs.isNotEmpty) ...[
          SectionHeader('Needs you', trailing: '${needs.length}'),
          for (final c in needs) _tile(context, queue, c),
        ],
        SectionHeader('Waiting', trailing: '${waiting.length}'),
        if (waiting.isEmpty) const ListTile(title: Text('Nothing is waiting.')),
        for (final c in waiting) _tile(context, queue, c),
        if (sent.isNotEmpty) ...[
          SectionHeader('Sent this session', trailing: '${sent.length}'),
          for (final c in sent)
            ListTile(dense: true, leading: const Icon(Icons.check), title: Text(c.label), subtitle: Text(c.note ?? 'accepted')),
        ],
      ]),
    );
  }

  Widget _tile(BuildContext context, QueueController queue, PendingCommand c) {
    final theme = Theme.of(context);
    final when = '${formatWhenDate(c.createdAt)} ${TimeOfDay.fromDateTime(c.createdAt).format(context)}';
    return Card(
      key: Key('outbox-${c.id}'),
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(c.needsPerson ? Icons.error_outline : Icons.cloud_upload_outlined,
                color: c.needsPerson ? theme.colorScheme.error : null),
            const SizedBox(width: 8),
            Expanded(child: Text(c.label, style: theme.textTheme.titleSmall)),
            StatusChip(c.status.name, tone: c.needsPerson ? theme.colorScheme.error : null),
          ]),
          const SizedBox(height: 4),
          Text('Captured $when${c.attempts > 0 ? ' · ${c.attempts} attempt(s)' : ''}',
              style: theme.textTheme.bodySmall),
          if (c.needsPerson) ...[
            const SizedBox(height: 4),
            Text(describe(c), key: Key('outbox-why-${c.id}')),
          ] else if (c.lastError != null) ...[
            const SizedBox(height: 4),
            Text('Last try: ${c.lastError}', style: theme.textTheme.bodySmall),
          ],
          if (c.needsPerson)
            Row(mainAxisAlignment: MainAxisAlignment.end, children: [
              if (c.status == CommandStatus.rejected && c.lastCode != 'forbidden')
                TextButton(key: Key('outbox-retry-${c.id}'), onPressed: () => queue.retry(c.id), child: const Text('Try again')),
              TextButton(
                key: Key('outbox-discard-${c.id}'),
                onPressed: () async {
                  final ok = await showDialog<bool>(
                    context: context,
                    builder: (_) => AlertDialog(
                      title: const Text('Discard this change?'),
                      content: Text('“${c.label}” is removed from this device. It was not applied in ARGUS.'),
                      actions: [
                        TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Keep')),
                        FilledButton(
                            key: const Key('outbox-discard-ok'),
                            onPressed: () => Navigator.pop(context, true),
                            child: const Text('Discard')),
                      ],
                    ),
                  );
                  if (ok == true) await queue.discard(c.id);
                },
                child: const Text('Discard'),
              ),
            ]),
        ]),
      ),
    );
  }
}

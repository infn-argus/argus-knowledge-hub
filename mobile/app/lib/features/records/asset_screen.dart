import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../domain/models.dart';
import '../../widgets/common.dart';

/// Equipment or a Position, next to the machine: what it is, what is installed there now (or
/// where this unit is installed), and the open tickets and documents that concern it
/// (flutter-app-design §5.3).
class AssetScreen extends ConsumerWidget {
  const AssetScreen({super.key, required this.uid});

  final String uid;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = ref.watch(assetDetailProvider(uid));
    return Scaffold(
      appBar: AppBar(title: Text(r.value?.key ?? 'Record')),
      floatingActionButton: r.value == null
          ? null
          : FloatingActionButton.extended(
              key: const Key('asset-report'),
              onPressed: () => context.push('/report/$uid'),
              icon: const Icon(Icons.report_problem_outlined),
              label: const Text('Report a problem'),
            ),
      body: r.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ProblemView(e, onRetry: () => ref.invalidate(assetDetailProvider(uid))),
        data: (a) => RefreshIndicator(
          onRefresh: () => ref.refresh(assetDetailProvider(uid).future),
          child: _AssetBody(a),
        ),
      ),
    );
  }
}

class _AssetBody extends StatelessWidget {
  const _AssetBody(this.a);

  final AssetDetail a;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final current = a.current;
    final attrs = a.attributes.entries.where((e) => e.value != null && e.value.toString().isNotEmpty).toList();
    final openTickets = a.tickets.where((t) => t.open).toList();
    return ListView(padding: const EdgeInsets.only(bottom: 32), children: [
      if (a.recordStatus == 'Merged')
        const NoticeBar(icon: Icons.merge_type, text: 'This record was merged into another. Use the surviving record.', severe: true),
      if (a.restricted != null)
        NoticeBar(icon: Icons.lock_outline, text: 'Restricted: ${a.restricted}. Do not share its details.'),
      if (a.processing)
        const NoticeBar(icon: Icons.sync, text: 'ARGUS is still processing recent changes. Relations may be incomplete.'),
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(a.name, key: const Key('asset-name'), style: theme.textTheme.headlineSmall),
          const SizedBox(height: 6),
          Wrap(spacing: 8, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
            StatusChip(a.isPosition ? 'Position' : 'Equipment', tone: theme.colorScheme.primary),
            StatusChip(a.type),
            if (a.recordStatus != 'Active') StatusChip(a.recordStatus, tone: theme.colorScheme.error),
            SelectableText(a.key, style: theme.textTheme.bodySmall),
          ]),
          if (a.typePath.length > 1) ...[
            const SizedBox(height: 6),
            Text(a.typePath.join(' › '), style: theme.textTheme.bodySmall),
          ],
        ]),
      ),
      SectionHeader(a.isPosition ? 'Installed here now' : 'Installed at now'),
      if (current.isEmpty)
        ListTile(
          leading: const Icon(Icons.remove_circle_outline),
          title: Text(a.isPosition ? 'Nothing is recorded as installed here.' : 'Not recorded as installed anywhere.'),
        )
      else
        for (final i in current) _installation(context, i),
      if (a.installations.length > current.length)
        ExpansionTile(
          title: Text('History (${a.installations.length - current.length})'),
          children: [for (final i in a.installations.where((i) => !current.contains(i))) _installation(context, i)],
        ),
      SectionHeader('Open tickets', trailing: '${openTickets.length} of ${a.tickets.length}'),
      if (openTickets.isEmpty) const ListTile(title: Text('No open tickets.')),
      for (final t in openTickets)
        ListTile(
          leading: const Icon(Icons.confirmation_number_outlined),
          title: Text(t.title, maxLines: 2, overflow: TextOverflow.ellipsis),
          subtitle: Text([t.state, if (t.priority != null) t.priority].join(' · ')),
          onTap: () => context.push('/ticket/${t.uid}'),
        ),
      SectionHeader('Documents', trailing: '${a.documents.length}'),
      if (a.documents.isEmpty) const ListTile(title: Text('No documents apply.')),
      for (final d in a.documents)
        ListTile(
          leading: Icon(d.reviewOverdue ? Icons.warning_amber : Icons.description_outlined,
              color: d.reviewOverdue ? theme.colorScheme.error : null),
          title: Text('${d.code} · ${d.title}', maxLines: 2, overflow: TextOverflow.ellipsis),
          subtitle: Text([d.state ?? 'no revision', if (d.reviewOverdue) 'review overdue'].join(' · ')),
          onTap: () => context.push('/document/${d.uid}'),
        ),
      if (attrs.isNotEmpty) ...[
        const SectionHeader('Attributes'),
        for (final e in attrs)
          ListTile(
            dense: true,
            title: Text(e.key),
            subtitle: SelectableText(e.value is Map || e.value is List ? e.value.toString() : '${e.value}'),
          ),
      ],
    ]);
  }

  Widget _installation(BuildContext context, InstallationInfo i) {
    final other = a.isPosition ? i.asset : i.position;
    final when = [
      if (i.from?.nominal != null) 'since ${formatWhenDate(i.from!.nominal)}',
      if (i.until?.nominal != null) 'until ${formatWhenDate(i.until!.nominal)}',
    ].join(' ');
    return ListTile(
      leading: Icon(a.isPosition ? Icons.memory : Icons.place_outlined),
      title: Text(other?.label ?? 'Unknown'),
      subtitle: Text([
        i.temporalState,
        if (i.status != 'Confirmed') i.status,
        if (i.certainty == 'possible') 'uncertain dates',
        if (when.isNotEmpty) when,
      ].join(' · ')),
      onTap: other?.uid == null ? null : () => context.push('/asset/${other!.uid}'),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../app/providers.dart';
import '../../core/problem.dart';
import '../../domain/capture.dart' show AttachmentInfo;
import '../../domain/models.dart';
import '../../widgets/auth_image.dart';
import '../../widgets/common.dart';
import '../../widgets/rich_content.dart';
import 'relation_graph_screen.dart';

/// Equipment or a Position, next to the machine: what it is, what is installed there now (or
/// where this unit is installed), what it connects to, the open tickets and documents that
/// concern it, its files, and its recent activity (flutter-app-design §5.3).
class AssetScreen extends ConsumerWidget {
  const AssetScreen({super.key, required this.uid});

  final String uid;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = ref.watch(assetDetailProvider(uid));
    return Scaffold(
      appBar: AppBar(title: Text(r.value?.name ?? 'Record'), actions: [
        if (r.value != null && r.value!.recordStatus != 'Merged')
          IconButton(
            key: const Key('asset-edit'),
            tooltip: 'Edit',
            icon: const Icon(Icons.edit_outlined),
            onPressed: () => context.push('/asset/$uid/edit'),
          ),
      ]),
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
          onRefresh: () async {
            ref.invalidate(assetCommentsProvider(uid));
            ref.invalidate(assetHistoryProvider(uid));
            ref.invalidate(assetAttachmentsProvider(uid));
            final _ = await ref.refresh(assetDetailProvider(uid).future);
          },
          child: _AssetBody(a),
        ),
      ),
    );
  }
}

class _AssetBody extends ConsumerStatefulWidget {
  const _AssetBody(this.a);

  final AssetDetail a;

  @override
  ConsumerState<_AssetBody> createState() => _AssetBodyState();
}

class _AssetBodyState extends ConsumerState<_AssetBody> {
  final _comment = TextEditingController();
  String _commentKey = const Uuid().v4();
  bool _sending = false;

  AssetDetail get a => widget.a;

  @override
  void dispose() {
    _comment.dispose();
    super.dispose();
  }

  Future<void> _sendComment() async {
    final text = _comment.text.trim();
    if (text.isEmpty) return;
    final session = ref.read(sessionProvider).value;
    setState(() => _sending = true);
    try {
      await ref.read(assetRepositoryProvider).comment(a.uid, _commentKey, session?.userLabel ?? 'field app', text);
      _comment.clear();
      _commentKey = const Uuid().v4();
      ref.invalidate(assetCommentsProvider(a.uid));
    } on Problem catch (p) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(p.message)));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final current = a.current;
    final attrs = a.attributes.entries.where((e) => e.value != null && e.value.toString().isNotEmpty).toList();
    final defsByKey = {for (final d in ref.watch(schemaAttributesProvider(a.schemaUid)).value ?? const []) d.key: d};
    final openTickets = a.tickets.where((t) => t.open).toList();
    final comments = ref.watch(assetCommentsProvider(a.uid)).value ?? const [];
    final history = ref.watch(assetHistoryProvider(a.uid)).value ?? const [];
    final attachments = ref.watch(assetAttachmentsProvider(a.uid)).value ?? const [];
    final activity = [
      ...comments.map((c) => _Activity(at: c.at, icon: Icons.chat_bubble_outline, author: c.author, text: c.body)),
      ...history.map((h) => _Activity(at: h.at, icon: Icons.history, author: h.author, text: h.details, kind: h.type)),
    ]..sort((x, y) => (y.at ?? DateTime(0)).compareTo(x.at ?? DateTime(0)));

    return ListView(key: const Key('asset-body-list'), padding: const EdgeInsets.only(bottom: 32), children: [
      if (a.recordStatus == 'Merged')
        const NoticeBar(icon: Icons.merge_type, text: 'This record was merged into another. Use the surviving record.', severe: true),
      if (a.restricted != null)
        NoticeBar(icon: Icons.lock_outline, text: 'Restricted: ${a.restricted}. Do not share its details.'),
      if (a.processing)
        const NoticeBar(icon: Icons.sync, text: 'ARGUS is still processing recent changes. Relations may be incomplete.'),
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (a.avatarIconUid != null) ...[
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: AuthImage(a.avatarIconUid!, width: 56, height: 56, fit: BoxFit.cover),
            ),
            const SizedBox(width: 12),
          ],
          Expanded(
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
      if (a.isPosition)
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Align(
            alignment: Alignment.centerLeft,
            child: OutlinedButton.icon(
              key: const Key('asset-replace'),
              onPressed: () => context.push('/replace/${a.uid}'),
              icon: const Icon(Icons.swap_horiz),
              label: Text(current.isEmpty ? 'Install a unit' : 'Replace the unit'),
            ),
          ),
        ),
      if (a.installations.length > current.length)
        ExpansionTile(
          title: Text('History (${a.installations.length - current.length})'),
          children: [for (final i in a.installations.where((i) => !current.contains(i))) _installation(context, i)],
        ),
      SectionHeader('Connections', trailing: '${a.relations.length}'),
      if (a.relations.isEmpty)
        const ListTile(title: Text('Nothing else is connected to this record.'))
      else ...[
        if (a.outbound.isNotEmpty) _RelationGroup(title: 'Outbound', items: a.outbound, icon: Icons.call_made),
        if (a.inbound.isNotEmpty) _RelationGroup(title: 'Inbound', items: a.inbound, icon: Icons.call_received),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          child: Align(
            alignment: Alignment.centerLeft,
            child: OutlinedButton.icon(
              key: const Key('asset-graph'),
              onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => RelationGraphScreen(rootUid: a.uid, rootName: a.name))),
              icon: const Icon(Icons.hub_outlined),
              label: const Text('View as a graph'),
            ),
          ),
        ),
      ],
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
      SectionHeader('Files', trailing: '${attachments.length}'),
      if (attachments.isEmpty) const ListTile(title: Text('No files yet.')),
      if (attachments.isNotEmpty)
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Wrap(spacing: 8, runSpacing: 8, children: [
            for (final f in attachments) _attachmentTile(context, f),
          ]),
        ),
      if (attrs.isNotEmpty) ...[
        const SectionHeader('Attributes'),
        for (final e in attrs)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(defsByKey[e.key]?.name ?? e.key, style: theme.textTheme.labelMedium?.copyWith(color: theme.colorScheme.outline)),
              const SizedBox(height: 2),
              defsByKey[e.key]?.type == 'reference' && e.value is String
                  ? _ReferenceValue(e.value as String)
                  : e.value is Map || e.value is List
                      ? SelectableText(e.value.toString())
                      : RichContent('${e.value}'),
            ]),
          ),
      ],
      const SectionHeader('Activity'),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Row(children: [
          Expanded(
            child: TextField(
              key: const Key('asset-comment-field'),
              controller: _comment,
              decoration: const InputDecoration(hintText: 'Add a comment…', isDense: true),
              onSubmitted: (_) => _sendComment(),
            ),
          ),
          IconButton(
            key: const Key('asset-comment-send'),
            icon: _sending
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                : const Icon(Icons.send),
            onPressed: _sending ? null : _sendComment,
          ),
        ]),
      ),
      if (activity.isEmpty) const ListTile(title: Text('Nothing recorded yet.')),
      for (final e in activity)
        ListTile(
          leading: Icon(e.icon),
          title: Text(e.text, maxLines: 4, overflow: TextOverflow.ellipsis),
          subtitle: Text([e.author, if (e.kind != null) e.kind!, if (e.at != null) formatWhenDate(e.at)].join(' · ')),
        ),
    ]);
  }

  Widget _attachmentTile(BuildContext context, AttachmentInfo f) {
    final isImage = (f.mimeType ?? '').startsWith('image/');
    return InkWell(
      onTap: () => showDialog(
        context: context,
        builder: (_) => Dialog(
          child: isImage
              ? InteractiveViewer(child: AuthImage(f.uid, fit: BoxFit.contain))
              : Padding(padding: const EdgeInsets.all(16), child: Text(f.filename)),
        ),
      ),
      child: Container(
        width: 84,
        height: 84,
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(8), border: Border.all(color: Theme.of(context).dividerColor)),
        clipBehavior: Clip.antiAlias,
        child: isImage
            ? AuthImage(f.uid, width: 84, height: 84)
            : Center(
                child: Padding(
                  padding: const EdgeInsets.all(6),
                  child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                    const Icon(Icons.attach_file),
                    Text(f.filename, maxLines: 2, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodySmall, textAlign: TextAlign.center),
                  ]),
                ),
              ),
      ),
    );
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

/// A reference attribute's stored uid, shown by the name of what it points at and tappable to open it —
/// not the bare uid a reference is stored as (flutter-app-design §5.4, mirroring the web's attribute
/// view, which resolves a reference the same way).
class _ReferenceValue extends ConsumerWidget {
  const _ReferenceValue(this.uid);

  final String uid;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final brief = ref.watch(assetBriefProvider(uid));
    return brief.when(
      loading: () => Text(uid, style: Theme.of(context).textTheme.bodySmall),
      error: (_, _) => SelectableText(uid),
      data: (b) => b == null
          ? SelectableText(uid)
          : InkWell(
              onTap: () => context.push('/asset/${b.uid}'),
              child: Text(b.label, style: TextStyle(color: Theme.of(context).colorScheme.primary, decoration: TextDecoration.underline)),
            ),
    );
  }
}

class _Activity {
  const _Activity({required this.at, required this.icon, required this.author, required this.text, this.kind});
  final DateTime? at;
  final IconData icon;
  final String author;
  final String text;
  final String? kind;
}

class _RelationGroup extends StatelessWidget {
  const _RelationGroup({required this.title, required this.items, required this.icon});

  final String title;
  final List<RelationItem> items;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final byRelation = <String, List<RelationItem>>{};
    for (final r in items) {
      byRelation.putIfAbsent(r.relation, () => []).add(r);
    }
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: Theme.of(context).textTheme.labelLarge),
        for (final entry in byRelation.entries) ...[
          Padding(
            padding: const EdgeInsets.only(top: 4, bottom: 2),
            child: Text(entry.key.replaceAll('_', ' '), style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Theme.of(context).colorScheme.outline)),
          ),
          for (final r in entry.value)
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: Icon(icon, size: 18),
              title: Text(r.name),
              subtitle: Text(r.type),
              onTap: () => context.push('/asset/${r.uid}'),
            ),
        ],
      ]),
    );
  }
}

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app/providers.dart';
import '../../app/queue.dart';
import '../../domain/models.dart';
import '../../widgets/common.dart';

/// Home: find a record by scanning its label or by typing (flutter-app-design §5.1).
class HomeScreen extends ConsumerStatefulWidget {
  const HomeScreen({super.key});

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen> {
  final _query = TextEditingController();
  Timer? _debounce;
  String _q = '';

  @override
  void dispose() {
    _debounce?.cancel();
    _query.dispose();
    super.dispose();
  }

  void _changed(String v) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () => setState(() => _q = v.trim()));
  }

  void _submit(String v) {
    final text = v.trim();
    if (text.isEmpty) return;
    // Enter on a label value (a key, an inventory number, a Jira key) goes straight to lookup.
    context.push('/lookup/${Uri.encodeComponent(text)}');
  }

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(sessionProvider).value;
    return Scaffold(
      appBar: AppBar(
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('ARGUS Field'),
          if (session?.workspaceName != null)
            Text(session!.workspaceName!, style: Theme.of(context).textTheme.labelMedium),
        ]),
        actions: [
          const _Unsent(),
          IconButton(
            key: const Key('home-ask'),
            tooltip: 'Ask the assistant',
            onPressed: () => context.push('/ask'),
            icon: const Icon(Icons.smart_toy_outlined),
          ),
          const _InboxBell(),
          PopupMenuButton<String>(
            key: const Key('home-menu'),
            onSelected: (v) {
              switch (v) {
                case 'register':
                  context.push('/register');
                case 'reviews':
                  context.push('/reviews');
                case 'workspace':
                  context.push('/workspace');
                case 'diagnostics':
                  context.push('/diagnostics');
                case 'signout':
                  _signOut(context, ref);
              }
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'register', child: Text('Register equipment')),
              PopupMenuItem(value: 'reviews', child: Text('Review items')),
              PopupMenuItem(value: 'workspace', child: Text('Switch workspace')),
              PopupMenuItem(value: 'diagnostics', child: Text('About and diagnostics')),
              PopupMenuItem(value: 'signout', child: Text('Sign out')),
            ],
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('home-scan'),
        onPressed: () => context.push('/scan'),
        icon: const Icon(Icons.qr_code_scanner),
        label: const Text('Scan label'),
      ),
      body: Column(children: [
        const _UpdateBanner(),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: TextField(
            key: const Key('home-search'),
            controller: _query,
            textInputAction: TextInputAction.search,
            decoration: InputDecoration(
              prefixIcon: const Icon(Icons.search),
              hintText: 'Key, name, serial, ticket or document',
              border: const OutlineInputBorder(),
              suffixIcon: _query.text.isEmpty
                  ? null
                  : IconButton(
                      icon: const Icon(Icons.clear),
                      onPressed: () {
                        _query.clear();
                        setState(() => _q = '');
                      }),
            ),
            onChanged: _changed,
            onSubmitted: _submit,
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
          child: Row(children: [
            Expanded(
              child: OutlinedButton.icon(
                key: const Key('home-tickets'),
                onPressed: () => context.push('/tickets'),
                icon: const Icon(Icons.confirmation_number_outlined),
                label: const Text('Tickets'),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: OutlinedButton.icon(
                key: const Key('home-documents'),
                onPressed: () => context.push('/documents'),
                icon: const Icon(Icons.description_outlined),
                label: const Text('Documents'),
              ),
            ),
          ]),
        ),
        Expanded(child: _q.length < 2 ? const _Cockpit() : _Results(q: _q)),
      ]),
    );
  }
}

/// Signing out wipes the device (§5.6). Unsent changes would be lost: the person sees them first.
Future<void> _signOut(BuildContext context, WidgetRef ref) async {
  final unsent = ref.read(queueProvider.notifier).unsent;
  if (unsent.isNotEmpty) {
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Sign out and lose unsent changes?'),
        content: Text('These are on this device only and would be removed:\n'
            '${unsent.map((c) => '• ${c.label}').join('\n')}'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Stay signed in')),
          FilledButton(
              key: const Key('signout-anyway'),
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Sign out anyway')),
        ],
      ),
    );
    if (ok != true) return;
  }
  await ref.read(sessionProvider.notifier).signOut();
}

class _Unsent extends ConsumerWidget {
  const _Unsent();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final all = ref.watch(queueProvider).value ?? const [];
    final n = all.where((c) => c.open || c.needsPerson).length;
    if (n == 0) return const SizedBox.shrink();
    return IconButton(
      key: const Key('home-outbox'),
      tooltip: 'Unsent changes',
      onPressed: () => context.push('/outbox'),
      icon: Badge(label: Text('$n'), child: const Icon(Icons.cloud_upload_outlined)),
    );
  }
}

class _InboxBell extends ConsumerWidget {
  const _InboxBell();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final unread = (ref.watch(notificationsProvider).value ?? const []).where((n) => !n.read).length;
    return IconButton(
      key: const Key('home-inbox'),
      tooltip: 'Notifications',
      onPressed: () => context.push('/inbox'),
      icon: Badge(isLabelVisible: unread > 0, label: Text('$unread'), child: const Icon(Icons.notifications_none)),
    );
  }
}

/// The operations cockpit, what home shows before a search: assigned to me, open tickets, the equipment they
/// pile up on, documents waiting for review, and recent activity — the web's home, from the same overview.
/// Without it (offline, or not yet loaded) the scanning hint still shows.
class _Cockpit extends ConsumerWidget {
  const _Cockpit();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = ref.watch(cockpitProvider);
    final c = r.value;
    return RefreshIndicator(
      onRefresh: () async => ref.invalidate(cockpitProvider),
      child: ListView(key: const Key('home-cockpit'), padding: const EdgeInsets.only(bottom: 88), children: [
        if (r.isLoading && c == null) const LinearProgressIndicator(),
        if (c == null) const _Hint(),
        if (c != null) ...[
          if (c.mine.isNotEmpty) ...[
            SectionHeader('Assigned to me', trailing: '${c.mine.length}'),
            for (final t in c.mine) _CockpitTile(t),
          ],
          if (c.openTickets != null)
            ListTile(
              key: const Key('cockpit-open-tickets'),
              leading: const Icon(Icons.confirmation_number_outlined),
              title: Text('${c.openTickets} open ticket${c.openTickets == 1 ? '' : 's'}'),
              subtitle: c.byState.isEmpty
                  ? null
                  : Text(c.byState.entries.where((e) => e.value > 0).map((e) => '${e.key} ${e.value}').join(' · ')),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => context.push('/tickets'),
            ),
          if (c.hotspots.isNotEmpty) ...[
            const SectionHeader('Equipment needing attention'),
            for (final a in c.hotspots) _CockpitTile(a),
          ],
          if (c.reviewOverdue.isNotEmpty || c.awaitingReview.isNotEmpty) ...[
            const SectionHeader('Documents to review'),
            for (final d in c.reviewOverdue) _CockpitTile(d, warning: 'review overdue'),
            for (final d in c.awaitingReview) _CockpitTile(d, warning: 'waiting for approval'),
          ],
          const SectionHeader('Recent activity'),
          if (c.recent.isEmpty) const ListTile(title: Text('Nothing yet.')),
          for (final x in c.recent) _CockpitTile(x, showWhen: true),
        ],
      ]),
    );
  }
}

class _CockpitTile extends StatelessWidget {
  const _CockpitTile(this.item, {this.warning, this.showWhen = false});

  final CockpitItem item;
  final String? warning;
  final bool showWhen;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final icon = switch (item.kind) {
      RecordKind.ticket => Icons.confirmation_number_outlined,
      RecordKind.document => Icons.description_outlined,
      _ => Icons.memory,
    };
    return ListTile(
      key: Key('cockpit-${item.kind.name}-${item.uid}'),
      dense: true,
      leading: Icon(icon, color: warning != null ? theme.colorScheme.error : null),
      title: Text(item.label, maxLines: 1, overflow: TextOverflow.ellipsis),
      subtitle: Text([
        ?warning,
        if ((item.sub ?? '').isNotEmpty) item.sub!,
      ].join(' · ')),
      trailing: item.count != null
          ? Badge(label: Text('${item.count}'))
          : showWhen && item.at != null
              ? Text(_ago(item.at!), style: theme.textTheme.bodySmall)
              : null,
      onTap: () => context.push(item.path),
    );
  }
}

String _ago(DateTime at) {
  final d = DateTime.now().difference(at);
  if (d.inMinutes < 1) return 'now';
  if (d.inHours < 1) return '${d.inMinutes} min';
  if (d.inDays < 1) return '${d.inHours} h';
  if (d.inDays < 30) return '${d.inDays} d';
  return formatWhenDate(at);
}

/// A newer release is out: offer to download it (an APK installs over this one as an update). Dismissed for
/// this run only — it comes back on the next start until the app is updated.
class _UpdateBanner extends ConsumerStatefulWidget {
  const _UpdateBanner();

  @override
  ConsumerState<_UpdateBanner> createState() => _UpdateBannerState();
}

class _UpdateBannerState extends ConsumerState<_UpdateBanner> {
  bool _dismissed = false;

  @override
  Widget build(BuildContext context) {
    final update = ref.watch(updateCheckProvider).value;
    if (update == null || _dismissed) return const SizedBox.shrink();
    return MaterialBanner(
      key: const Key('home-update'),
      leading: const Icon(Icons.system_update),
      content: Text('Version ${update.version} is available.'),
      actions: [
        TextButton(onPressed: () => setState(() => _dismissed = true), child: const Text('Later')),
        FilledButton(
          key: const Key('home-update-download'),
          onPressed: () => launchUrl(Uri.parse(update.url), mode: LaunchMode.externalApplication),
          child: const Text('Download'),
        ),
      ],
    );
  }
}

class _Hint extends StatelessWidget {
  const _Hint();

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Text(
            'Scan the label on the equipment or its position, or type at least two characters.\n'
            'Press Enter to look up an exact label value, such as an old Jira key.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
          ),
        ),
      );
}

class _Results extends ConsumerWidget {
  const _Results({required this.q});

  final String q;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = ref.watch(searchProvider(q));
    return r.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => ProblemView(e, onRetry: () => ref.invalidate(searchProvider(q))),
      data: (res) => res.isEmpty
          ? Center(child: Text('Nothing matches "$q".'))
          : ListView(padding: const EdgeInsets.only(bottom: 96), children: [
              if (res.assets.isNotEmpty) ...[
                SectionHeader('Assets', trailing: '${res.assets.length}'),
                for (final t in res.assets) _hit(context, t, Icons.memory),
              ],
              if (res.tickets.isNotEmpty) ...[
                SectionHeader('Tickets', trailing: '${res.tickets.length}'),
                for (final t in res.tickets) _hit(context, t, Icons.confirmation_number_outlined),
              ],
              if (res.documents.isNotEmpty) ...[
                SectionHeader('Documents', trailing: '${res.documents.length}'),
                for (final t in res.documents) _hit(context, t, Icons.description_outlined),
              ],
            ]),
    );
  }

  Widget _hit(BuildContext context, LinkTarget t, IconData icon) => ListTile(
        leading: Icon(icon),
        title: Text(t.title ?? t.uid, maxLines: 2, overflow: TextOverflow.ellipsis),
        subtitle: t.subtitle == null ? null : Text(t.subtitle!),
        onTap: () => context.push(t.route),
      );
}

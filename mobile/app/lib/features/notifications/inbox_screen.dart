import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../widgets/common.dart';

/// What happened to the person's tickets, and to the equipment and documents they follow, in every workspace
/// they can open (flutter-app-design §11): a notification from another workspace opens its record there. A
/// notification says only what the person may see.
class InboxScreen extends ConsumerWidget {
  const InboxScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = ref.watch(notificationsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Notifications'), actions: [
        if ((r.value ?? const []).any((n) => !n.read))
          TextButton(
            key: const Key('inbox-read-all'),
            onPressed: () async {
              try {
                await ref.read(notificationRepositoryProvider).markAllRead();
              } catch (_) {}
              ref.invalidate(notificationsProvider);
            },
            child: const Text('Mark all read'),
          ),
      ]),
      body: r.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ProblemView(e, onRetry: () => ref.invalidate(notificationsProvider)),
        data: (items) => items.isEmpty
            ? const Center(child: Text('Nothing new.'))
            : RefreshIndicator(
                onRefresh: () => ref.refresh(notificationsProvider.future),
                child: ListView(children: [
                  for (final n in items)
                    ListTile(
                      key: Key('notification-${n.id}'),
                      leading: Icon(n.read ? Icons.notifications_none : Icons.notifications_active,
                          color: n.read ? null : Theme.of(context).colorScheme.primary),
                      title: Text(n.title,
                          style: n.read ? null : const TextStyle(fontWeight: FontWeight.w600)),
                      subtitle: Text([
                        n.workspaceName,
                        if (n.at != null) formatWhenDate(n.at),
                      ].whereType<String>().join(' · ')),
                      onTap: n.route == null
                          ? null
                          : () async {
                              if (!n.read) {
                                try {
                                  await ref.read(notificationRepositoryProvider).markRead(n.id);
                                } catch (_) {}
                                ref.invalidate(notificationsProvider);
                              }
                              if (context.mounted) context.push(n.route!);
                            },
                    ),
                ]),
              ),
      ),
    );
  }
}

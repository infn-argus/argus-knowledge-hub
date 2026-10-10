import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../app/providers.dart';

/// Follow a piece of equipment ('asset') or a document: each change to it becomes a notification, in
/// whichever workspace it is.
class FollowButton extends ConsumerWidget {
  const FollowButton({super.key, required this.subject, required this.uid});

  final String subject;
  final String uid;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(followingProvider((subject, uid)));
    final on = state.value ?? false;
    return IconButton(
      key: Key('follow-$subject'),
      tooltip: on ? 'Following: tap to stop' : 'Follow: be told of each change',
      icon: Icon(on ? Icons.notifications_active : Icons.notifications_none_outlined),
      onPressed: state.isLoading && !state.hasValue
          ? null
          : () async {
              try {
                await ref.read(notificationRepositoryProvider).setFollowing(subject, uid, !on);
                ref.invalidate(followingProvider((subject, uid)));
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                      content: Text(on ? 'No longer following.' : 'Following: you will be told of each change.')));
                }
              } catch (e) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not change it now.')));
                }
              }
            },
    );
  }
}

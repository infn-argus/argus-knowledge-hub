import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/providers.dart';

/// The server refused this version (426 `client_too_old`). Nothing is read or sent until the
/// app is updated from the organization's store (revision §24.2).
class UpdateScreen extends ConsumerWidget {
  const UpdateScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final minimum = ref.watch(updateRequiredProvider);
    final config = ref.watch(configProvider);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.system_update, size: 56, color: Theme.of(context).colorScheme.primary),
              const SizedBox(height: 12),
              Text('Update required', style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 12),
              Text(
                'This version (${config.appVersion}) is no longer accepted by ARGUS. '
                'Install version $minimum or later from the company app store, then open the app again.',
                textAlign: TextAlign.center,
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

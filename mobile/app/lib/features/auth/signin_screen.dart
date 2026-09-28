import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/providers.dart';
import '../../core/problem.dart';

class SplashScreen extends StatelessWidget {
  const SplashScreen({super.key});

  @override
  Widget build(BuildContext context) => const Scaffold(body: Center(child: CircularProgressIndicator()));
}

/// Sign-in: the organization's identity provider in the system browser (§6.1). A token field
/// exists only in development and staging builds, for the web build and local testing.
class SignInScreen extends ConsumerStatefulWidget {
  const SignInScreen({super.key});

  @override
  ConsumerState<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends ConsumerState<SignInScreen> {
  final _token = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _token.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
    } on Problem catch (p) {
      setState(() => _error = p.code == ProblemCode.unauthenticated && p.status == 401
          ? 'ARGUS did not accept these credentials.'
          : p.message);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final config = ref.watch(configProvider);
    final auth = ref.watch(authenticatorProvider);
    final reason = ref.watch(signOutReasonProvider);
    final controller = ref.read(sessionProvider.notifier);
    final theme = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: ListView(padding: const EdgeInsets.all(24), shrinkWrap: true, children: [
              Icon(Icons.qr_code_scanner, size: 56, color: theme.colorScheme.primary),
              const SizedBox(height: 12),
              Text('ARGUS Field', textAlign: TextAlign.center, style: theme.textTheme.headlineSmall),
              const SizedBox(height: 4),
              Text('Look up equipment, positions, tickets and procedures next to the machine.',
                  textAlign: TextAlign.center, style: theme.textTheme.bodyMedium),
              if (config.environment != 'production') ...[
                const SizedBox(height: 12),
                Center(child: Chip(label: Text('${config.environment} · ${config.apiBase}'))),
              ],
              if (reason != null) ...[
                const SizedBox(height: 16),
                Card(
                  color: theme.colorScheme.secondaryContainer,
                  child: Padding(padding: const EdgeInsets.all(12), child: Text(reason)),
                ),
              ],
              const SizedBox(height: 24),
              if (auth.supportsOidc)
                FilledButton.icon(
                  key: const Key('signin-oidc'),
                  onPressed: _busy ? null : () => _run(controller.signInWithOidc),
                  icon: const Icon(Icons.login),
                  label: const Text('Sign in with your organization account'),
                ),
              if (config.allowsDeveloperToken) ...[
                if (auth.supportsOidc) const Padding(padding: EdgeInsets.symmetric(vertical: 16), child: Divider()),
                TextField(
                  key: const Key('signin-token'),
                  controller: _token,
                  obscureText: true,
                  enabled: !_busy,
                  decoration: const InputDecoration(
                    labelText: 'Access token (development only)',
                    border: OutlineInputBorder(),
                  ),
                  onSubmitted: (_) => _run(() => controller.signInWithToken(_token.text)),
                ),
                const SizedBox(height: 12),
                OutlinedButton(
                  key: const Key('signin-token-submit'),
                  onPressed: _busy ? null : () => _run(() => controller.signInWithToken(_token.text)),
                  child: const Text('Sign in with token'),
                ),
              ],
              if (_busy) const Padding(padding: EdgeInsets.only(top: 16), child: LinearProgressIndicator()),
              if (_error != null) ...[
                const SizedBox(height: 16),
                Text(_error!, style: TextStyle(color: theme.colorScheme.error), textAlign: TextAlign.center),
              ],
            ]),
          ),
        ),
      ),
    );
  }
}

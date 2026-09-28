import 'package:flutter/material.dart';

import '../core/problem.dart';

/// A problem, said the same way on every screen (flutter-app-design §3.4): what happened and what
/// the person can do, with a retry when retrying can help.
class ProblemView extends StatelessWidget {
  const ProblemView(this.error, {super.key, this.onRetry});

  final Object error;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final p = error is Problem ? error as Problem : null;
    final (icon, title, text) = switch (p?.code) {
      ProblemCode.notFound => (
          Icons.search_off,
          'Not found',
          'ARGUS has no record here that you can see. It may not exist, or it may be restricted.'
        ),
      ProblemCode.forbidden => (Icons.lock_outline, 'Not allowed', p!.message),
      ProblemCode.offline => (Icons.cloud_off, 'No connection', p!.message),
      _ => (Icons.error_outline, 'Something went wrong', p?.message ?? error.toString()),
    };
    final retry = onRetry != null && p?.code != ProblemCode.notFound && p?.code != ProblemCode.forbidden;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 48, color: Theme.of(context).colorScheme.outline),
          const SizedBox(height: 12),
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Text(text, textAlign: TextAlign.center),
          if (retry) ...[
            const SizedBox(height: 16),
            FilledButton.tonal(onPressed: onRetry, child: const Text('Try again')),
          ],
        ]),
      ),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader(this.title, {super.key, this.trailing});

  final String title;
  final String? trailing;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 20, 16, 4),
        child: Row(children: [
          Expanded(
            child: Text(title.toUpperCase(),
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                      letterSpacing: 0.8,
                      color: Theme.of(context).colorScheme.primary,
                    )),
          ),
          if (trailing != null) Text(trailing!, style: Theme.of(context).textTheme.labelMedium),
        ]),
      );
}

/// A strip across the top of a record for things that change how it may be used.
class NoticeBar extends StatelessWidget {
  const NoticeBar({super.key, required this.icon, required this.text, this.severe = false});

  final IconData icon;
  final String text;
  final bool severe;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final bg = severe ? scheme.errorContainer : scheme.secondaryContainer;
    final fg = severe ? scheme.onErrorContainer : scheme.onSecondaryContainer;
    return Container(
      width: double.infinity,
      color: bg,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(children: [
        Icon(icon, color: fg),
        const SizedBox(width: 12),
        Expanded(child: Text(text, style: TextStyle(color: fg))),
      ]),
    );
  }
}

class StatusChip extends StatelessWidget {
  const StatusChip(this.label, {super.key, this.tone});

  final String label;
  final Color? tone;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        border: Border.all(color: tone ?? scheme.outline),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(label, style: Theme.of(context).textTheme.labelSmall?.copyWith(color: tone ?? scheme.onSurfaceVariant)),
    );
  }
}

String formatWhenDate(DateTime? d) =>
    d == null ? '' : '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

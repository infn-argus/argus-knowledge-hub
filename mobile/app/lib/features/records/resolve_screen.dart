import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../app/providers.dart';
import '../../core/link_parser.dart';
import '../../core/problem.dart';
import '../../domain/models.dart' show LinkTarget, inWorkspace;
import '../../widgets/common.dart';

/// Opens a link or a label through the server's resolver, then replaces itself with the record.
/// A record that does not exist and one this person may not see look the same (I-MOB-6).
class ResolveScreen extends ConsumerWidget {
  const ResolveScreen({super.key, required this.path});

  final String path;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    ref.listen(resolveProvider(path), (_, next) {
      final target = next.value;
      // Found by a piece of the code: asked first, whether to remember the whole code (below).
      if (target == null || target.matchedCode != null) return;
      if (target.viaPort != null) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Found through its network port ${target.viaPort}')));
      }
      context.pushReplacement(target.route);
    });
    final r = ref.watch(resolveProvider(path));
    final label = Uri.decodeComponent(path.split('/').last);
    return Scaffold(
      appBar: AppBar(title: Text(label)),
      body: r.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        data: (target) => target.matchedCode != null
            ? _FoundByPart(target)
            : const Center(child: CircularProgressIndicator()),
        error: (e, _) => e is Problem && e.code == ProblemCode.ambiguous
            ? _Candidates(e)
            : Column(children: [
                // A web link no record carries: probably someone else's code (a manufacturer's), not opened.
                if (e is Problem && e.code == ProblemCode.notFound && foreignLinkHost(label) != null)
                  NoticeBar(
                    key: const Key('resolve-foreign-link'),
                    icon: Icons.link_off,
                    text: 'This code is a link to ${foreignLinkHost(label)}. No ARGUS record carries it as a label, '
                        'and it was not opened.',
                  ),
                Expanded(child: ProblemView(e, onRetry: () => ref.invalidate(resolveProvider(path)))),
                // An unknown label on a unit in hand: register it, or remember it on the unit it is on; never
                // invent a unit from a name (I-MOB-6).
                if (e is Problem && e.code == ProblemCode.notFound && path.startsWith('/lookup/'))
                  SafeArea(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                        FilledButton.tonalIcon(
                          key: const Key('resolve-register'),
                          onPressed: () => context.pushReplacement('/register?label=${Uri.encodeComponent(label)}'),
                          icon: const Icon(Icons.add_box_outlined),
                          label: const Text('Register this unit'),
                        ),
                        const SizedBox(height: 8),
                        OutlinedButton.icon(
                          key: const Key('resolve-remember'),
                          onPressed: () => _rememberOnChosen(context, ref, label),
                          icon: const Icon(Icons.bookmark_add_outlined),
                          label: const Text('Remember this code on a unit'),
                        ),
                      ]),
                    ),
                  ),
              ]),
      ),
    );
  }
}

/// The label kind a remembered code is kept as: a web address is printed as a QR code; anything else is a
/// barcode of some kind (a DataMatrix, a Code 128…).
String rememberedKind(String code) => code.contains('://') ? 'qrcode' : 'barcode';

Future<void> _remember(BuildContext context, WidgetRef ref, String assetUid, String code) =>
    ref.read(assetRepositoryProvider).addLabel(assetUid, const Uuid().v4(), rememberedKind(code), code);

/// The unit the code is on, chosen by the person: the code is then its label, and the next scan opens it.
Future<void> _rememberOnChosen(BuildContext context, WidgetRef ref, String code) async {
  final chosen = await showModalBottomSheet<LinkTarget>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (_) => const _ChooseUnit(),
  );
  if (chosen == null || !context.mounted) return;
  try {
    await _remember(context, ref, chosen.uid, code);
    if (context.mounted) context.pushReplacement(chosen.route);
  } on Problem catch (p) {
    if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(p.message)));
  }
}

/// Found by a piece of the scanned code — the serial inside a manufacturer's code — not by the whole code.
/// Remembering the whole code on the record makes the next scan find it at once.
class _FoundByPart extends ConsumerStatefulWidget {
  const _FoundByPart(this.target);

  final LinkTarget target;

  @override
  ConsumerState<_FoundByPart> createState() => _FoundByPartState();
}

class _FoundByPartState extends ConsumerState<_FoundByPart> {
  bool _saving = false;
  String? _error;

  Future<void> _rememberAndOpen() async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await _remember(context, ref, widget.target.uid, widget.target.matchedCode!);
      if (mounted) context.pushReplacement(widget.target.route);
    } on Problem catch (p) {
      if (mounted) setState(() => _error = p.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = widget.target;
    return ListView(padding: const EdgeInsets.all(16), children: [
      Text('Found ${t.title ?? t.key ?? 'a record'}', style: Theme.of(context).textTheme.titleLarge),
      if (t.subtitle != null || t.key != null)
        Text([t.key, t.subtitle].whereType<String>().join(' · '), style: Theme.of(context).textTheme.bodySmall),
      const SizedBox(height: 12),
      Text('by “${t.matchedPart}”, found inside this code. Remember the whole code on it, so the next scan opens '
          'it directly?'),
      if (_error != null) ...[
        const SizedBox(height: 8),
        Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
      ],
      const SizedBox(height: 16),
      FilledButton.icon(
        key: const Key('resolve-remember-open'),
        onPressed: _saving ? null : _rememberAndOpen,
        icon: const Icon(Icons.bookmark_add_outlined),
        label: Text(_saving ? 'Remembering…' : 'Remember and open'),
      ),
      const SizedBox(height: 8),
      OutlinedButton(
        key: const Key('resolve-just-open'),
        onPressed: _saving ? null : () => context.pushReplacement(t.route),
        child: const Text('Just open it'),
      ),
    ]);
  }
}

/// Search for the unit a code is on.
class _ChooseUnit extends ConsumerStatefulWidget {
  const _ChooseUnit();

  @override
  ConsumerState<_ChooseUnit> createState() => _ChooseUnitState();
}

class _ChooseUnitState extends ConsumerState<_ChooseUnit> {
  String _q = '';

  @override
  Widget build(BuildContext context) {
    final results = _q.trim().length < 2 ? null : ref.watch(searchProvider(_q.trim()));
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 0, 16, 16 + MediaQuery.of(context).viewInsets.bottom),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Text('Which unit is it on?', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        TextField(
          key: const Key('remember-search'),
          autofocus: true,
          decoration: const InputDecoration(
              labelText: 'Key, name or serial', border: OutlineInputBorder(), prefixIcon: Icon(Icons.search)),
          onChanged: (v) => setState(() => _q = v),
        ),
        ConstrainedBox(
          constraints: const BoxConstraints(maxHeight: 320),
          child: results == null
              ? const SizedBox.shrink()
              : results.when(
                  loading: () => const Padding(padding: EdgeInsets.all(16), child: LinearProgressIndicator()),
                  error: (e, _) => Padding(padding: const EdgeInsets.all(16), child: Text(e.toString())),
                  data: (s) => ListView(shrinkWrap: true, children: [
                    for (final a in s.assets)
                      ListTile(
                        key: Key('remember-on-${a.uid}'),
                        leading: const Icon(Icons.memory),
                        title: Text(a.title ?? a.uid),
                        subtitle: Text([a.key, a.subtitle].whereType<String>().join(' · ')),
                        onTap: () => Navigator.pop(context, a),
                      ),
                    if (s.assets.isEmpty) const ListTile(title: Text('No unit found')),
                  ]),
                ),
        ),
      ]),
    );
  }
}

/// A label value held by more than one record: nothing is opened; the person picks the one in
/// front of them, comparing what the labels say (A67).
class _Candidates extends StatelessWidget {
  const _Candidates(this.problem);

  final Problem problem;

  @override
  Widget build(BuildContext context) => ListView(children: [
        NoticeBar(icon: Icons.call_split, text: problem.message),
        for (final c in problem.candidates)
          ListTile(
            key: Key('candidate-${c['uid']}'),
            leading: const Icon(Icons.memory),
            title: Text(c['name']?.toString() ?? c['key'].toString()),
            subtitle: Text([
              c['key'],
              c['type'],
              if (c['workspace_id'] != null) 'in ${c['workspace_id']}',
              ...((c['attributes'] as Map?) ?? const {}).entries.map((e) => '${e.key} ${e.value}'),
            ].whereType<Object>().join(' · ')),
            onTap: () => context.pushReplacement(inWorkspace('/asset/${c['uid']}', c['workspace_id']?.toString())),
          ),
      ]);
}

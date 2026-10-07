import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/providers.dart';
import '../../core/problem.dart';
import '../../domain/models.dart';
import '../../widgets/common.dart';
import '../capture/proposal_tile.dart';

/// Editing a record's attributes, respecting what its type actually allows: the field kind (a date picks
/// from a calendar, a yes/no is a switch, an enumeration is its own options — never a bare text box for
/// everything), whether it is required, a value pattern it must match, and whether it holds one value or
/// several (flutter-app-design §5.4, mirrored from the web form's AttributeInput.tsx). A text field can
/// also be read from a photo: not full nameplate OCR, the same AI reading the registration photo already
/// uses, scoped to the one field asked for and never applied until the person takes it (§23.11).
class AssetEditScreen extends ConsumerStatefulWidget {
  const AssetEditScreen({super.key, required this.uid});

  final String uid;

  @override
  ConsumerState<AssetEditScreen> createState() => _AssetEditScreenState();
}

class _AssetEditScreenState extends ConsumerState<AssetEditScreen> {
  final Map<String, List<TextEditingController>> _text = {};
  final Map<String, List<bool>> _bool = {};
  final Map<String, List<String?>> _choice = {};
  bool _saving = false;
  String? _error;
  String? _scanning;

  void _ensure(AttributeDef def, Map<String, Object?> attrs) {
    if (_text.containsKey(def.key) || _bool.containsKey(def.key) || _choice.containsKey(def.key)) return;
    final raw = attrs[def.key];
    final values = def.multiValue ? (raw is List ? raw : (raw == null ? const [] : [raw])) : [raw];
    if (def.type == 'boolean') {
      _bool[def.key] = values.isEmpty ? [false] : values.map((v) => v == true).toList();
    } else if (def.type == 'enumeration' || (def.type == 'reference' && def.referenceSchemaUid != null)) {
      // A reference is stored as the target's uid, same shape as an enumeration's stored label — one
      // slot per current value, picked rather than typed (see _referencePicker).
      _choice[def.key] = values.isEmpty ? [null] : values.map((v) => v?.toString()).toList();
    } else {
      _text[def.key] = (values.isEmpty ? [null] : values).map((v) => TextEditingController(text: v?.toString() ?? '')).toList();
    }
  }

  @override
  void dispose() {
    for (final list in _text.values) {
      for (final c in list) {
        c.dispose();
      }
    }
    super.dispose();
  }

  Object? _convert(AttributeDef def, String text) {
    final t = text.trim();
    if (t.isEmpty) return null;
    switch (def.type) {
      case 'integer':
        return int.tryParse(t);
      case 'float':
        return double.tryParse(t);
      default:
        return t;
    }
  }

  String? _validate(AttributeDef def, String text) {
    final t = text.trim();
    if (t.isEmpty) return null; // required/min-cardinality is checked across all values, not per field
    if ((def.type == 'integer' && int.tryParse(t) == null) || (def.type == 'float' && double.tryParse(t) == null)) {
      return 'Not a number';
    }
    if (def.regex != null && def.regex!.isNotEmpty && !RegExp(def.regex!).hasMatch(t)) {
      return "Doesn't match the required pattern";
    }
    if ((def.type == 'date' || def.type == 'datetime') && DateTime.tryParse(t) == null) {
      return 'Not a date (YYYY-MM-DD)';
    }
    return null;
  }

  Future<void> _pickDate(AttributeDef def, TextEditingController c) async {
    final initial = DateTime.tryParse(c.text) ?? DateTime.now();
    final date = await showDatePicker(context: context, initialDate: initial, firstDate: DateTime(1990), lastDate: DateTime(2100));
    if (date == null) return;
    setState(() => c.text = def.type == 'datetime' ? date.toIso8601String() : date.toIso8601String().substring(0, 10));
  }

  Future<void> _scan(AttributeDef def, TextEditingController c, AssetDetail a) async {
    final photo = await ref.read(photoSourceProvider).take();
    if (photo == null || !mounted) return;
    final draft = {
      'uid': a.uid,
      'name': a.name,
      'schema_uid': a.schemaUid,
      'attributes': {for (final e in a.attributes.entries) e.key: e.value},
    };
    setState(() => _scanning = def.key);
    try {
      final result = await ref.read(intakeRepositoryProvider).assistAssetPhoto(photo, draft);
      if (!mounted) return;
      final proposal = result.proposals['attributes.${def.key}'];
      if (proposal == null) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Nothing read for ${def.name} in that photo.')));
        return;
      }
      // The sheet only reports whether "Use" was pressed; the field itself is changed afterwards, once
      // the sheet has finished closing — mutating this screen's state from inside the sheet's own
      // subtree, in the same tap that pops it, is what a Flutter Navigator assertion exists to catch.
      final taken = await showModalBottomSheet<bool>(
        context: context,
        builder: (sheetContext) => SafeArea(
          child: ProposalTile(proposal, onTake: () => Navigator.of(sheetContext).pop(true)),
        ),
      );
      if (taken == true && mounted) setState(() => c.text = proposal.display);
    } on Problem catch (p) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('The photo could not be read (${p.message}).')));
    } finally {
      if (mounted) setState(() => _scanning = null);
    }
  }

  Future<void> _save(AssetDetail a, List<AttributeDef> defs) async {
    String? problem;
    for (final def in defs.where((d) => d.editable)) {
      final count = def.type == 'boolean'
          ? _bool[def.key]!.length
          : _choice[def.key] != null
              ? _choice[def.key]!.where((v) => v != null).length
              : _text[def.key]!.where((c) => c.text.trim().isNotEmpty).length;
      if (def.required && count == 0) problem ??= '${def.name} is required.';
      if (def.minCardinality != null && count < def.minCardinality!) problem ??= '${def.name} needs at least ${def.minCardinality}.';
      if (def.maxCardinality != null && count > def.maxCardinality!) problem ??= '${def.name} allows at most ${def.maxCardinality}.';
      if (_text[def.key] != null) {
        for (final c in _text[def.key]!) {
          final e = _validate(def, c.text);
          if (e != null) problem ??= '${def.name}: $e';
        }
      }
    }
    if (problem != null) {
      setState(() => _error = problem);
      return;
    }
    final attributes = <String, Object?>{...a.attributes};
    for (final def in defs.where((d) => d.editable)) {
      if (def.type == 'boolean') {
        final values = _bool[def.key]!;
        attributes[def.key] = def.multiValue ? values : values.first;
      } else if (_choice[def.key] != null) {
        final values = _choice[def.key]!.whereType<String>().toList();
        attributes[def.key] = def.multiValue ? values : (values.isEmpty ? null : values.first);
      } else {
        final values = _text[def.key]!.map((c) => _convert(def, c.text)).whereType<Object>().toList();
        attributes[def.key] = def.multiValue ? values : (values.isEmpty ? null : values.first);
      }
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await ref
          .read(assetRepositoryProvider)
          .save(a, attributes, key: '${a.uid}-${DateTime.now().millisecondsSinceEpoch}');
      ref.invalidate(assetDetailProvider(a.uid));
      if (mounted) context.pop();
    } on Problem catch (p) {
      if (p.code == ProblemCode.stale) {
        ref.invalidate(assetDetailProvider(a.uid));
        setState(() => _error = 'Someone changed this record meanwhile. Reopen it and try again.');
      } else {
        setState(() => _error = p.message);
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final detail = ref.watch(assetDetailProvider(widget.uid));
    return Scaffold(
      appBar: AppBar(title: Text('Edit ${detail.value?.name ?? ''}')),
      body: detail.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ProblemView(e, onRetry: () => ref.invalidate(assetDetailProvider(widget.uid))),
        data: (a) => Consumer(builder: (context, ref, _) {
          final defsAsync = ref.watch(schemaAttributesProvider(a.schemaUid));
          return defsAsync.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (e, _) => ProblemView(e, onRetry: () => ref.invalidate(schemaAttributesProvider(a.schemaUid))),
            data: (defs) {
              for (final def in defs) {
                _ensure(def, a.attributes);
              }
              final editable = defs.where((d) => d.editable).toList();
              final readOnly = defs.where((d) => !d.editable).toList();
              return ListView(
                key: const Key('asset-edit-list'),
                padding: const EdgeInsets.all(16),
                children: [
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: NoticeBar(icon: Icons.error_outline, text: _error!, severe: true),
                    ),
                  for (final def in editable) _field(def, a),
                  if (readOnly.isNotEmpty) ...[
                    const SectionHeader('Edited on the web'),
                    for (final def in readOnly)
                      ListTile(
                        dense: true,
                        title: Text(def.name),
                        subtitle: Text('${def.type} — this kind of field is edited in the web app, not here'),
                      ),
                  ],
                  const SizedBox(height: 16),
                  FilledButton(
                    key: const Key('asset-edit-save'),
                    onPressed: _saving ? null : () => _save(a, defs),
                    child: _saving ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('Save'),
                  ),
                ],
              );
            },
          );
        }),
      ),
    );
  }

  Widget _field(AttributeDef def, AssetDetail a) {
    final label = def.name + (def.required ? ' *' : '');
    switch (def.type) {
      case 'boolean':
        final values = _bool[def.key]!;
        return SwitchListTile(
          key: Key('attr-${def.key}'),
          title: Text(label),
          value: values.first,
          onChanged: (v) => setState(() => values[0] = v),
        );
      case 'enumeration':
        final values = _choice[def.key]!;
        final current = values.first;
        // The option's label is what is stored and what the web form writes (AttributeInput.tsx), not its
        // id — an enumeration's id and label commonly differ ("in_service" / "In service"). Deduplicated by
        // label, and with the record's current value kept as an extra item when it names no listed option
        // (a value from before the list changed, or edited outside the form): a dropdown must offer exactly
        // one item equal to its value or Flutter refuses to render it at all.
        final labels = <String>{};
        final options = <DropdownMenuItem<String>>[];
        for (final o in def.options) {
          if (labels.add(o.value)) options.add(DropdownMenuItem(value: o.value, child: Text(o.value)));
        }
        if (current != null && labels.add(current)) {
          options.add(DropdownMenuItem(value: current, child: Text('$current (not in the current list)')));
        }
        return Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: DropdownButtonFormField<String>(
            key: Key('attr-${def.key}'),
            initialValue: current,
            decoration: InputDecoration(labelText: label),
            items: [const DropdownMenuItem(value: null, child: Text('—')), ...options],
            onChanged: (v) => setState(() => values[0] = v),
          ),
        );
      case 'reference':
        if (def.referenceSchemaUid == null) return _plainTextField(def, a, label);
        return _referencePicker(def, label);
      default:
        return _plainTextField(def, a, label);
    }
  }

  /// A reference attribute offers the candidates of its target type (and its descendant types, when
  /// includeChildren) to pick among, instead of a free-text uid field the person could never type
  /// correctly — the same choice the web form's ReferenceInput/AssetPicker makes.
  Widget _referencePicker(AttributeDef def, String label) {
    final values = _choice[def.key]!;
    final candidatesAsync = ref.watch(referenceCandidatesProvider((def.referenceSchemaUid!, def.includeChildren)));
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        for (final (i, uid) in values.indexed)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
              Expanded(
                child: candidatesAsync.when(
                  loading: () => const Padding(padding: EdgeInsets.symmetric(vertical: 12), child: LinearProgressIndicator()),
                  error: (e, _) => Text('Could not load choices: $e'),
                  data: (candidates) => _ReferenceField(
                    key: Key('attr-${def.key}-$i'),
                    label: i == 0 ? label : null,
                    candidates: candidates,
                    value: uid,
                    onChanged: (v) => setState(() => values[i] = v),
                  ),
                ),
              ),
              if (def.multiValue)
                IconButton(
                  icon: const Icon(Icons.remove_circle_outline),
                  onPressed: values.length <= (def.minCardinality ?? 0) ? null : () => setState(() => values.removeAt(i)),
                ),
            ]),
          ),
        if (def.multiValue && (def.maxCardinality == null || values.length < def.maxCardinality!))
          TextButton.icon(
            onPressed: () => setState(() => values.add(null)),
            icon: const Icon(Icons.add),
            label: Text('Add ${def.name.toLowerCase()}'),
          ),
      ]),
    );
  }

  Widget _plainTextField(AttributeDef def, AssetDetail a, String label) {
    final controllers = _text[def.key]!;
    return Padding(
        padding: const EdgeInsets.only(bottom: 4),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            for (final (i, c) in controllers.indexed)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Expanded(
                    child: TextField(
                      key: Key('attr-${def.key}-$i'),
                      controller: c,
                      maxLines: def.type == 'text' ? 4 : 1,
                      keyboardType: def.type == 'integer' || def.type == 'float' ? TextInputType.number : TextInputType.text,
                      readOnly: def.type == 'date' || def.type == 'datetime',
                      onTap: def.type == 'date' || def.type == 'datetime' ? () => _pickDate(def, c) : null,
                      decoration: InputDecoration(
                        labelText: i == 0 ? label : null,
                        hintText: def.type == 'date' || def.type == 'datetime' ? 'Tap to choose' : null,
                        helperText: i == 0 ? def.description : null,
                      ),
                    ),
                  ),
                  if (def.type == 'string' || def.type == 'text')
                    IconButton(
                      key: Key('attr-${def.key}-$i-scan'),
                      tooltip: 'Read from a photo',
                      // Not an animated spinner: the read is a single quick request, and a widget that
                      // animates forever never lets a test (or, just as real, a slow device) settle on it.
                      icon: Icon(_scanning == def.key ? Icons.hourglass_top : Icons.document_scanner_outlined),
                      onPressed: _scanning != null ? null : () => _scan(def, c, a),
                    ),
                  if (def.multiValue)
                    IconButton(
                      icon: const Icon(Icons.remove_circle_outline),
                      onPressed: controllers.length <= (def.minCardinality ?? 0)
                          ? null
                          : () => setState(() => controllers.removeAt(i).dispose()),
                    ),
                ]),
              ),
            if (def.multiValue && (def.maxCardinality == null || controllers.length < def.maxCardinality!))
              TextButton.icon(
                onPressed: () => setState(() => controllers.add(TextEditingController())),
                icon: const Icon(Icons.add),
                label: Text('Add ${def.name.toLowerCase()}'),
              ),
        ]));
  }
}

/// A search-as-you-type picker among a reference attribute's candidate records, instead of a bare
/// uid text field — mirrors the web form's AssetPicker (name/key search, pick-only: there is no way
/// to commit a value that isn't one of the candidates).
class _ReferenceField extends StatelessWidget {
  const _ReferenceField({super.key, required this.candidates, required this.value, required this.onChanged, this.label});

  final List<RecordBrief> candidates;
  final String? value;
  final ValueChanged<String?> onChanged;
  final String? label;

  @override
  Widget build(BuildContext context) {
    RecordBrief? selected;
    for (final c in candidates) {
      if (c.uid == value) {
        selected = c;
        break;
      }
    }
    return RawAutocomplete<RecordBrief>(
      initialValue: TextEditingValue(text: selected?.label ?? (value ?? '')),
      displayStringForOption: (o) => o.label,
      optionsBuilder: (v) {
        final q = v.text.trim().toLowerCase();
        final matches = q.isEmpty
            ? candidates
            : candidates.where((c) => (c.name ?? '').toLowerCase().contains(q) || (c.key ?? '').toLowerCase().contains(q));
        return matches.take(30);
      },
      onSelected: (o) => onChanged(o.uid),
      fieldViewBuilder: (context, controller, focusNode, onFieldSubmitted) => TextField(
        controller: controller,
        focusNode: focusNode,
        decoration: InputDecoration(
          labelText: label,
          hintText: 'Search ${candidates.isEmpty ? '' : candidates.first.type ?? ''}…',
          suffixIcon: value == null
              ? null
              : IconButton(
                  icon: const Icon(Icons.clear),
                  onPressed: () {
                    controller.clear();
                    onChanged(null);
                  },
                ),
        ),
      ),
      optionsViewBuilder: (context, onSelected, options) => Align(
        alignment: Alignment.topLeft,
        child: Material(
          elevation: 4,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 240),
            child: ListView(
              padding: EdgeInsets.zero,
              shrinkWrap: true,
              children: [
                for (final o in options)
                  ListTile(dense: true, title: Text(o.label), onTap: () => onSelected(o)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

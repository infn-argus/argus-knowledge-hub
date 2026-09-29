import 'package:flutter/material.dart';

import '../../domain/capture.dart';

/// One value the assistant proposed: what it is, how sure, and where it was read (revision §23.11,
/// §24.6). Nothing is used until the person takes it.
class ProposalTile extends StatelessWidget {
  const ProposalTile(this.proposal, {super.key, required this.onTake});

  final Proposal proposal;
  final VoidCallback onTake;

  static String fieldName(String field) => switch (field) {
        'title' => 'Title',
        'description' => 'Details',
        'schema_uid' => 'Kind',
        'name' => 'Name',
        'key' => 'Key',
        _ => field.startsWith('attributes.')
            ? field.substring(11).replaceAll('argus_', '').replaceAll('_', ' ')
            : field,
      };

  @override
  Widget build(BuildContext context) {
    final p = proposal;
    final scheme = Theme.of(context).colorScheme;
    final how = [
      if (p.confidence != null) '${(p.confidence! * 100).round()}% sure',
      if (p.evidence != null) 'read in “${p.evidence}”' else if (p.method == 'draft') 'drafted from your words',
      if (!p.grounded) 'not found in what you gave: check it',
    ].join(' · ');
    return ListTile(
      key: Key('proposal-${p.field}'),
      leading: Icon(p.weak ? Icons.help_outline : Icons.auto_awesome, color: p.weak ? scheme.tertiary : scheme.primary),
      title: Text('${fieldName(p.field)}: ${p.display}', maxLines: 3, overflow: TextOverflow.ellipsis),
      subtitle: Text(how),
      trailing: TextButton(key: Key('take-${p.field}'), onPressed: onTake, child: const Text('Use')),
    );
  }
}

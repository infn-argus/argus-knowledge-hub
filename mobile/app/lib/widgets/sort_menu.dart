import 'package:flutter/material.dart';

import '../data/browse_repository.dart';

/// Sort a list by name, creation or last change; choosing the current one again turns the order round.
class SortMenu extends StatelessWidget {
  const SortMenu({super.key, required this.order, required this.onChanged});

  final ListOrder order;
  final ValueChanged<ListOrder> onChanged;

  @override
  Widget build(BuildContext context) => PopupMenuButton<SortBy>(
        key: const Key('sort-menu'),
        tooltip: 'Sort',
        icon: const Icon(Icons.sort),
        onSelected: (by) => onChanged(by == order.by
            ? order.flipped()
            : ListOrder(by, descending: by != SortBy.name)), // times newest first, names A to Z
        itemBuilder: (_) => [
          for (final by in SortBy.values)
            PopupMenuItem(
              key: Key('sort-${by.name}'),
              value: by,
              child: Row(children: [
                SizedBox(
                  width: 28,
                  child: by == order.by
                      ? Icon(order.descending ? Icons.arrow_downward : Icons.arrow_upward, size: 18)
                      : null,
                ),
                Text(by.label),
              ]),
            ),
        ],
      );
}

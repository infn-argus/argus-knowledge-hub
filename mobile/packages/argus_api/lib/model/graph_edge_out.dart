//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class GraphEdgeOut {
  /// Returns a new [GraphEdgeOut] instance.
  GraphEdgeOut({
    required this.fromKind,
    required this.fromUid,
    required this.relation,
    required this.toKind,
    required this.toUid,
    required this.via,
  });

  String fromKind;

  String fromUid;

  String relation;

  String toKind;

  String toUid;

  String via;

  @override
  bool operator ==(Object other) => identical(this, other) || other is GraphEdgeOut &&
    other.fromKind == fromKind &&
    other.fromUid == fromUid &&
    other.relation == relation &&
    other.toKind == toKind &&
    other.toUid == toUid &&
    other.via == via;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (fromKind.hashCode) +
    (fromUid.hashCode) +
    (relation.hashCode) +
    (toKind.hashCode) +
    (toUid.hashCode) +
    (via.hashCode);

  @override
  String toString() => 'GraphEdgeOut[fromKind=$fromKind, fromUid=$fromUid, relation=$relation, toKind=$toKind, toUid=$toUid, via=$via]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'from_kind'] = this.fromKind;
      json[r'from_uid'] = this.fromUid;
      json[r'relation'] = this.relation;
      json[r'to_kind'] = this.toKind;
      json[r'to_uid'] = this.toUid;
      json[r'via'] = this.via;
    return json;
  }

  /// Returns a new [GraphEdgeOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static GraphEdgeOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "GraphEdgeOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "GraphEdgeOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return GraphEdgeOut(
        fromKind: mapValueOfType<String>(json, r'from_kind')!,
        fromUid: mapValueOfType<String>(json, r'from_uid')!,
        relation: mapValueOfType<String>(json, r'relation')!,
        toKind: mapValueOfType<String>(json, r'to_kind')!,
        toUid: mapValueOfType<String>(json, r'to_uid')!,
        via: mapValueOfType<String>(json, r'via')!,
      );
    }
    return null;
  }

  static List<GraphEdgeOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <GraphEdgeOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = GraphEdgeOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, GraphEdgeOut> mapFromJson(dynamic json) {
    final map = <String, GraphEdgeOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = GraphEdgeOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of GraphEdgeOut-objects as value to a dart map
  static Map<String, List<GraphEdgeOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<GraphEdgeOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = GraphEdgeOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'from_kind',
    'from_uid',
    'relation',
    'to_kind',
    'to_uid',
    'via',
  };
}


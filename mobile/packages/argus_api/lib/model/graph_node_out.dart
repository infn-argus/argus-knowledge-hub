//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class GraphNodeOut {
  /// Returns a new [GraphNodeOut] instance.
  GraphNodeOut({
    required this.depth,
    required this.kind,
    required this.label,
    this.restricted = false,
    this.state,
    this.sublabel,
    this.typeName,
    required this.uid,
  });

  int depth;

  String kind;

  String label;

  bool restricted;

  String? state;

  String? sublabel;

  String? typeName;

  String uid;

  @override
  bool operator ==(Object other) => identical(this, other) || other is GraphNodeOut &&
    other.depth == depth &&
    other.kind == kind &&
    other.label == label &&
    other.restricted == restricted &&
    other.state == state &&
    other.sublabel == sublabel &&
    other.typeName == typeName &&
    other.uid == uid;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (depth.hashCode) +
    (kind.hashCode) +
    (label.hashCode) +
    (restricted.hashCode) +
    (state == null ? 0 : state!.hashCode) +
    (sublabel == null ? 0 : sublabel!.hashCode) +
    (typeName == null ? 0 : typeName!.hashCode) +
    (uid.hashCode);

  @override
  String toString() => 'GraphNodeOut[depth=$depth, kind=$kind, label=$label, restricted=$restricted, state=$state, sublabel=$sublabel, typeName=$typeName, uid=$uid]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'depth'] = this.depth;
      json[r'kind'] = this.kind;
      json[r'label'] = this.label;
      json[r'restricted'] = this.restricted;
    if (this.state != null) {
      json[r'state'] = this.state;
    } else {
      json[r'state'] = null;
    }
    if (this.sublabel != null) {
      json[r'sublabel'] = this.sublabel;
    } else {
      json[r'sublabel'] = null;
    }
    if (this.typeName != null) {
      json[r'type_name'] = this.typeName;
    } else {
      json[r'type_name'] = null;
    }
      json[r'uid'] = this.uid;
    return json;
  }

  /// Returns a new [GraphNodeOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static GraphNodeOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "GraphNodeOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "GraphNodeOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return GraphNodeOut(
        depth: mapValueOfType<int>(json, r'depth')!,
        kind: mapValueOfType<String>(json, r'kind')!,
        label: mapValueOfType<String>(json, r'label')!,
        restricted: mapValueOfType<bool>(json, r'restricted') ?? false,
        state: mapValueOfType<String>(json, r'state'),
        sublabel: mapValueOfType<String>(json, r'sublabel'),
        typeName: mapValueOfType<String>(json, r'type_name'),
        uid: mapValueOfType<String>(json, r'uid')!,
      );
    }
    return null;
  }

  static List<GraphNodeOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <GraphNodeOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = GraphNodeOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, GraphNodeOut> mapFromJson(dynamic json) {
    final map = <String, GraphNodeOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = GraphNodeOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of GraphNodeOut-objects as value to a dart map
  static Map<String, List<GraphNodeOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<GraphNodeOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = GraphNodeOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'depth',
    'kind',
    'label',
    'uid',
  };
}


//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class GraphOut {
  /// Returns a new [GraphOut] instance.
  GraphOut({
    this.edges = const [],
    this.nodes = const [],
    required this.truncated,
  });

  List<GraphEdgeOut> edges;

  List<GraphNodeOut> nodes;

  bool truncated;

  @override
  bool operator ==(Object other) => identical(this, other) || other is GraphOut &&
    _deepEquality.equals(other.edges, edges) &&
    _deepEquality.equals(other.nodes, nodes) &&
    other.truncated == truncated;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (edges.hashCode) +
    (nodes.hashCode) +
    (truncated.hashCode);

  @override
  String toString() => 'GraphOut[edges=$edges, nodes=$nodes, truncated=$truncated]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'edges'] = this.edges;
      json[r'nodes'] = this.nodes;
      json[r'truncated'] = this.truncated;
    return json;
  }

  /// Returns a new [GraphOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static GraphOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "GraphOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "GraphOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return GraphOut(
        edges: GraphEdgeOut.listFromJson(json[r'edges']),
        nodes: GraphNodeOut.listFromJson(json[r'nodes']),
        truncated: mapValueOfType<bool>(json, r'truncated')!,
      );
    }
    return null;
  }

  static List<GraphOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <GraphOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = GraphOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, GraphOut> mapFromJson(dynamic json) {
    final map = <String, GraphOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = GraphOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of GraphOut-objects as value to a dart map
  static Map<String, List<GraphOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<GraphOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = GraphOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'edges',
    'nodes',
    'truncated',
  };
}


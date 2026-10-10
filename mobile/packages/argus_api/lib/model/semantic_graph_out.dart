//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class SemanticGraphOut {
  /// Returns a new [SemanticGraphOut] instance.
  SemanticGraphOut({
    this.available = true,
    this.basis,
    this.edges = const [],
    this.nodes = const [],
    this.reason,
  });

  bool available;

  String? basis;

  List<SemanticEdgeOut> edges;

  List<GraphNodeOut> nodes;

  String? reason;

  @override
  bool operator ==(Object other) => identical(this, other) || other is SemanticGraphOut &&
    other.available == available &&
    other.basis == basis &&
    _deepEquality.equals(other.edges, edges) &&
    _deepEquality.equals(other.nodes, nodes) &&
    other.reason == reason;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (available.hashCode) +
    (basis == null ? 0 : basis!.hashCode) +
    (edges.hashCode) +
    (nodes.hashCode) +
    (reason == null ? 0 : reason!.hashCode);

  @override
  String toString() => 'SemanticGraphOut[available=$available, basis=$basis, edges=$edges, nodes=$nodes, reason=$reason]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'available'] = this.available;
    if (this.basis != null) {
      json[r'basis'] = this.basis;
    } else {
      json[r'basis'] = null;
    }
      json[r'edges'] = this.edges;
      json[r'nodes'] = this.nodes;
    if (this.reason != null) {
      json[r'reason'] = this.reason;
    } else {
      json[r'reason'] = null;
    }
    return json;
  }

  /// Returns a new [SemanticGraphOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static SemanticGraphOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "SemanticGraphOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "SemanticGraphOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return SemanticGraphOut(
        available: mapValueOfType<bool>(json, r'available') ?? true,
        basis: mapValueOfType<String>(json, r'basis'),
        edges: SemanticEdgeOut.listFromJson(json[r'edges']),
        nodes: GraphNodeOut.listFromJson(json[r'nodes']),
        reason: mapValueOfType<String>(json, r'reason'),
      );
    }
    return null;
  }

  static List<SemanticGraphOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <SemanticGraphOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = SemanticGraphOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, SemanticGraphOut> mapFromJson(dynamic json) {
    final map = <String, SemanticGraphOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = SemanticGraphOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of SemanticGraphOut-objects as value to a dart map
  static Map<String, List<SemanticGraphOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<SemanticGraphOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = SemanticGraphOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'edges',
    'nodes',
  };
}


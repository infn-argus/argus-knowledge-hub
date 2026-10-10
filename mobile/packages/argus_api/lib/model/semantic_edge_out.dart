//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class SemanticEdgeOut {
  /// Returns a new [SemanticEdgeOut] instance.
  SemanticEdgeOut({
    required this.excerpt,
    required this.fromKind,
    required this.fromUid,
    required this.matched,
    this.relation = 'similar',
    required this.score,
    required this.toKind,
    required this.toUid,
  });

  String excerpt;

  String fromKind;

  String fromUid;

  String matched;

  String relation;

  num score;

  String toKind;

  String toUid;

  @override
  bool operator ==(Object other) => identical(this, other) || other is SemanticEdgeOut &&
    other.excerpt == excerpt &&
    other.fromKind == fromKind &&
    other.fromUid == fromUid &&
    other.matched == matched &&
    other.relation == relation &&
    other.score == score &&
    other.toKind == toKind &&
    other.toUid == toUid;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (excerpt.hashCode) +
    (fromKind.hashCode) +
    (fromUid.hashCode) +
    (matched.hashCode) +
    (relation.hashCode) +
    (score.hashCode) +
    (toKind.hashCode) +
    (toUid.hashCode);

  @override
  String toString() => 'SemanticEdgeOut[excerpt=$excerpt, fromKind=$fromKind, fromUid=$fromUid, matched=$matched, relation=$relation, score=$score, toKind=$toKind, toUid=$toUid]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'excerpt'] = this.excerpt;
      json[r'from_kind'] = this.fromKind;
      json[r'from_uid'] = this.fromUid;
      json[r'matched'] = this.matched;
      json[r'relation'] = this.relation;
      json[r'score'] = this.score;
      json[r'to_kind'] = this.toKind;
      json[r'to_uid'] = this.toUid;
    return json;
  }

  /// Returns a new [SemanticEdgeOut] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static SemanticEdgeOut? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "SemanticEdgeOut[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "SemanticEdgeOut[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return SemanticEdgeOut(
        excerpt: mapValueOfType<String>(json, r'excerpt')!,
        fromKind: mapValueOfType<String>(json, r'from_kind')!,
        fromUid: mapValueOfType<String>(json, r'from_uid')!,
        matched: mapValueOfType<String>(json, r'matched')!,
        relation: mapValueOfType<String>(json, r'relation') ?? 'similar',
        score: num.parse('${json[r'score']}'),
        toKind: mapValueOfType<String>(json, r'to_kind')!,
        toUid: mapValueOfType<String>(json, r'to_uid')!,
      );
    }
    return null;
  }

  static List<SemanticEdgeOut> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <SemanticEdgeOut>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = SemanticEdgeOut.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, SemanticEdgeOut> mapFromJson(dynamic json) {
    final map = <String, SemanticEdgeOut>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = SemanticEdgeOut.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of SemanticEdgeOut-objects as value to a dart map
  static Map<String, List<SemanticEdgeOut>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<SemanticEdgeOut>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = SemanticEdgeOut.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'excerpt',
    'from_kind',
    'from_uid',
    'matched',
    'score',
    'to_kind',
    'to_uid',
  };
}


//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class AIStatus {
  /// Returns a new [AIStatus] instance.
  AIStatus({
    required this.configured,
    required this.enabled,
    this.hasAsr = false,
    this.hasEmbeddings = false,
    this.hasRerank = false,
    this.hasTts = false,
    this.hasVision = false,
    this.inheritedFrom,
    this.model,
    this.reason,
    required this.validated,
  });

  bool configured;

  bool enabled;

  bool hasAsr;

  bool hasEmbeddings;

  bool hasRerank;

  bool hasTts;

  bool hasVision;

  String? inheritedFrom;

  String? model;

  String? reason;

  bool validated;

  @override
  bool operator ==(Object other) => identical(this, other) || other is AIStatus &&
    other.configured == configured &&
    other.enabled == enabled &&
    other.hasAsr == hasAsr &&
    other.hasEmbeddings == hasEmbeddings &&
    other.hasRerank == hasRerank &&
    other.hasTts == hasTts &&
    other.hasVision == hasVision &&
    other.inheritedFrom == inheritedFrom &&
    other.model == model &&
    other.reason == reason &&
    other.validated == validated;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (configured.hashCode) +
    (enabled.hashCode) +
    (hasAsr.hashCode) +
    (hasEmbeddings.hashCode) +
    (hasRerank.hashCode) +
    (hasTts.hashCode) +
    (hasVision.hashCode) +
    (inheritedFrom == null ? 0 : inheritedFrom!.hashCode) +
    (model == null ? 0 : model!.hashCode) +
    (reason == null ? 0 : reason!.hashCode) +
    (validated.hashCode);

  @override
  String toString() => 'AIStatus[configured=$configured, enabled=$enabled, hasAsr=$hasAsr, hasEmbeddings=$hasEmbeddings, hasRerank=$hasRerank, hasTts=$hasTts, hasVision=$hasVision, inheritedFrom=$inheritedFrom, model=$model, reason=$reason, validated=$validated]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'configured'] = this.configured;
      json[r'enabled'] = this.enabled;
      json[r'has_asr'] = this.hasAsr;
      json[r'has_embeddings'] = this.hasEmbeddings;
      json[r'has_rerank'] = this.hasRerank;
      json[r'has_tts'] = this.hasTts;
      json[r'has_vision'] = this.hasVision;
    if (this.inheritedFrom != null) {
      json[r'inherited_from'] = this.inheritedFrom;
    } else {
      json[r'inherited_from'] = null;
    }
    if (this.model != null) {
      json[r'model'] = this.model;
    } else {
      json[r'model'] = null;
    }
    if (this.reason != null) {
      json[r'reason'] = this.reason;
    } else {
      json[r'reason'] = null;
    }
      json[r'validated'] = this.validated;
    return json;
  }

  /// Returns a new [AIStatus] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static AIStatus? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "AIStatus[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "AIStatus[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return AIStatus(
        configured: mapValueOfType<bool>(json, r'configured')!,
        enabled: mapValueOfType<bool>(json, r'enabled')!,
        hasAsr: mapValueOfType<bool>(json, r'has_asr') ?? false,
        hasEmbeddings: mapValueOfType<bool>(json, r'has_embeddings') ?? false,
        hasRerank: mapValueOfType<bool>(json, r'has_rerank') ?? false,
        hasTts: mapValueOfType<bool>(json, r'has_tts') ?? false,
        hasVision: mapValueOfType<bool>(json, r'has_vision') ?? false,
        inheritedFrom: mapValueOfType<String>(json, r'inherited_from'),
        model: mapValueOfType<String>(json, r'model'),
        reason: mapValueOfType<String>(json, r'reason'),
        validated: mapValueOfType<bool>(json, r'validated')!,
      );
    }
    return null;
  }

  static List<AIStatus> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <AIStatus>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = AIStatus.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, AIStatus> mapFromJson(dynamic json) {
    final map = <String, AIStatus>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = AIStatus.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of AIStatus-objects as value to a dart map
  static Map<String, List<AIStatus>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<AIStatus>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = AIStatus.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'configured',
    'enabled',
    'validated',
  };
}


//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class ReplaceIn {
  /// Returns a new [ReplaceIn] instance.
  ReplaceIn({
    required this.at,
    this.condition,
    this.dryRun = false,
    this.evidence,
    required this.incomingUid,
    this.outgoingUid,
    required this.positionUid,
    this.precision = 'instant',
    this.reason = 'Replacement',
    this.seenInstallationUid,
    this.workReference,
  });

  DateTime at;

  String? condition;

  bool dryRun;

  Object? evidence;

  String incomingUid;

  String? outgoingUid;

  String positionUid;

  String precision;

  String reason;

  String? seenInstallationUid;

  String? workReference;

  @override
  bool operator ==(Object other) => identical(this, other) || other is ReplaceIn &&
    other.at == at &&
    other.condition == condition &&
    other.dryRun == dryRun &&
    other.evidence == evidence &&
    other.incomingUid == incomingUid &&
    other.outgoingUid == outgoingUid &&
    other.positionUid == positionUid &&
    other.precision == precision &&
    other.reason == reason &&
    other.seenInstallationUid == seenInstallationUid &&
    other.workReference == workReference;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (at.hashCode) +
    (condition == null ? 0 : condition!.hashCode) +
    (dryRun.hashCode) +
    (evidence == null ? 0 : evidence!.hashCode) +
    (incomingUid.hashCode) +
    (outgoingUid == null ? 0 : outgoingUid!.hashCode) +
    (positionUid.hashCode) +
    (precision.hashCode) +
    (reason.hashCode) +
    (seenInstallationUid == null ? 0 : seenInstallationUid!.hashCode) +
    (workReference == null ? 0 : workReference!.hashCode);

  @override
  String toString() => 'ReplaceIn[at=$at, condition=$condition, dryRun=$dryRun, evidence=$evidence, incomingUid=$incomingUid, outgoingUid=$outgoingUid, positionUid=$positionUid, precision=$precision, reason=$reason, seenInstallationUid=$seenInstallationUid, workReference=$workReference]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'at'] = this.at.toUtc().toIso8601String();
    if (this.condition != null) {
      json[r'condition'] = this.condition;
    } else {
      json[r'condition'] = null;
    }
      json[r'dry_run'] = this.dryRun;
    if (this.evidence != null) {
      json[r'evidence'] = this.evidence;
    } else {
      json[r'evidence'] = null;
    }
      json[r'incoming_uid'] = this.incomingUid;
    if (this.outgoingUid != null) {
      json[r'outgoing_uid'] = this.outgoingUid;
    } else {
      json[r'outgoing_uid'] = null;
    }
      json[r'position_uid'] = this.positionUid;
      json[r'precision'] = this.precision;
      json[r'reason'] = this.reason;
    if (this.seenInstallationUid != null) {
      json[r'seen_installation_uid'] = this.seenInstallationUid;
    } else {
      json[r'seen_installation_uid'] = null;
    }
    if (this.workReference != null) {
      json[r'work_reference'] = this.workReference;
    } else {
      json[r'work_reference'] = null;
    }
    return json;
  }

  /// Returns a new [ReplaceIn] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static ReplaceIn? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "ReplaceIn[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "ReplaceIn[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return ReplaceIn(
        at: mapDateTime(json, r'at', r'')!,
        condition: mapValueOfType<String>(json, r'condition'),
        dryRun: mapValueOfType<bool>(json, r'dry_run') ?? false,
        evidence: mapValueOfType<Object>(json, r'evidence'),
        incomingUid: mapValueOfType<String>(json, r'incoming_uid')!,
        outgoingUid: mapValueOfType<String>(json, r'outgoing_uid'),
        positionUid: mapValueOfType<String>(json, r'position_uid')!,
        precision: mapValueOfType<String>(json, r'precision') ?? 'instant',
        reason: mapValueOfType<String>(json, r'reason') ?? 'Replacement',
        seenInstallationUid: mapValueOfType<String>(json, r'seen_installation_uid'),
        workReference: mapValueOfType<String>(json, r'work_reference'),
      );
    }
    return null;
  }

  static List<ReplaceIn> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <ReplaceIn>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = ReplaceIn.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, ReplaceIn> mapFromJson(dynamic json) {
    final map = <String, ReplaceIn>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = ReplaceIn.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of ReplaceIn-objects as value to a dart map
  static Map<String, List<ReplaceIn>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<ReplaceIn>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = ReplaceIn.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'at',
    'incoming_uid',
    'position_uid',
  };
}


//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class DeviceIn {
  /// Returns a new [DeviceIn] instance.
  DeviceIn({
    required this.appVersion,
    required this.installationId,
    this.name,
    required this.platform,
  });

  String appVersion;

  String installationId;

  String? name;

  String platform;

  @override
  bool operator ==(Object other) => identical(this, other) || other is DeviceIn &&
    other.appVersion == appVersion &&
    other.installationId == installationId &&
    other.name == name &&
    other.platform == platform;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (appVersion.hashCode) +
    (installationId.hashCode) +
    (name == null ? 0 : name!.hashCode) +
    (platform.hashCode);

  @override
  String toString() => 'DeviceIn[appVersion=$appVersion, installationId=$installationId, name=$name, platform=$platform]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
      json[r'app_version'] = this.appVersion;
      json[r'installation_id'] = this.installationId;
    if (this.name != null) {
      json[r'name'] = this.name;
    } else {
      json[r'name'] = null;
    }
      json[r'platform'] = this.platform;
    return json;
  }

  /// Returns a new [DeviceIn] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static DeviceIn? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "DeviceIn[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "DeviceIn[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return DeviceIn(
        appVersion: mapValueOfType<String>(json, r'app_version')!,
        installationId: mapValueOfType<String>(json, r'installation_id')!,
        name: mapValueOfType<String>(json, r'name'),
        platform: mapValueOfType<String>(json, r'platform')!,
      );
    }
    return null;
  }

  static List<DeviceIn> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <DeviceIn>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = DeviceIn.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, DeviceIn> mapFromJson(dynamic json) {
    final map = <String, DeviceIn>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = DeviceIn.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of DeviceIn-objects as value to a dart map
  static Map<String, List<DeviceIn>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<DeviceIn>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = DeviceIn.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
    'app_version',
    'installation_id',
    'platform',
  };
}


//
// AUTO-GENERATED FILE, DO NOT MODIFY!
//
// @dart=2.18

// ignore_for_file: unused_element, unused_import
// ignore_for_file: always_put_required_named_parameters_first
// ignore_for_file: constant_identifier_names
// ignore_for_file: lines_longer_than_80_chars

part of openapi.api;

class PortIn {
  /// Returns a new [PortIn] instance.
  PortIn({
    this.linkSpeed,
    this.mac,
    this.portKind,
    this.portLabel = 'eth0',
  });

  String? linkSpeed;

  String? mac;

  String? portKind;

  String portLabel;

  @override
  bool operator ==(Object other) => identical(this, other) || other is PortIn &&
    other.linkSpeed == linkSpeed &&
    other.mac == mac &&
    other.portKind == portKind &&
    other.portLabel == portLabel;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (linkSpeed == null ? 0 : linkSpeed!.hashCode) +
    (mac == null ? 0 : mac!.hashCode) +
    (portKind == null ? 0 : portKind!.hashCode) +
    (portLabel.hashCode);

  @override
  String toString() => 'PortIn[linkSpeed=$linkSpeed, mac=$mac, portKind=$portKind, portLabel=$portLabel]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.linkSpeed != null) {
      json[r'link_speed'] = this.linkSpeed;
    } else {
      json[r'link_speed'] = null;
    }
    if (this.mac != null) {
      json[r'mac'] = this.mac;
    } else {
      json[r'mac'] = null;
    }
    if (this.portKind != null) {
      json[r'port_kind'] = this.portKind;
    } else {
      json[r'port_kind'] = null;
    }
      json[r'port_label'] = this.portLabel;
    return json;
  }

  /// Returns a new [PortIn] instance and imports its values from
  /// [value] if it's a [Map], null otherwise.
  // ignore: prefer_constructors_over_static_methods
  static PortIn? fromJson(dynamic value) {
    if (value is Map) {
      final json = value.cast<String, dynamic>();

      // Ensure that the map contains the required keys.
      // Note 1: the values aren't checked for validity beyond being non-null.
      // Note 2: this code is stripped in release mode!
      assert(() {
        requiredKeys.forEach((key) {
          assert(json.containsKey(key), 'Required key "PortIn[$key]" is missing from JSON.');
          assert(json[key] != null, 'Required key "PortIn[$key]" has a null value in JSON.');
        });
        return true;
      }());

      return PortIn(
        linkSpeed: mapValueOfType<String>(json, r'link_speed'),
        mac: mapValueOfType<String>(json, r'mac'),
        portKind: mapValueOfType<String>(json, r'port_kind'),
        portLabel: mapValueOfType<String>(json, r'port_label') ?? 'eth0',
      );
    }
    return null;
  }

  static List<PortIn> listFromJson(dynamic json, {bool growable = false,}) {
    final result = <PortIn>[];
    if (json is List && json.isNotEmpty) {
      for (final row in json) {
        final value = PortIn.fromJson(row);
        if (value != null) {
          result.add(value);
        }
      }
    }
    return result.toList(growable: growable);
  }

  static Map<String, PortIn> mapFromJson(dynamic json) {
    final map = <String, PortIn>{};
    if (json is Map && json.isNotEmpty) {
      json = json.cast<String, dynamic>(); // ignore: parameter_assignments
      for (final entry in json.entries) {
        final value = PortIn.fromJson(entry.value);
        if (value != null) {
          map[entry.key] = value;
        }
      }
    }
    return map;
  }

  // maps a json object with a list of PortIn-objects as value to a dart map
  static Map<String, List<PortIn>> mapListFromJson(dynamic json, {bool growable = false,}) {
    final map = <String, List<PortIn>>{};
    if (json is Map && json.isNotEmpty) {
      // ignore: parameter_assignments
      json = json.cast<String, dynamic>();
      for (final entry in json.entries) {
        map[entry.key] = PortIn.listFromJson(entry.value, growable: growable,);
      }
    }
    return map;
  }

  /// The list of required keys that must be present in a JSON.
  static const requiredKeys = <String>{
  };
}


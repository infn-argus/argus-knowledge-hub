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
    this.baud,
    this.flowControl,
    this.framing,
    this.linkSpeed,
    this.mac,
    this.operatingMode,
    this.portKind,
    this.portLabel = 'eth0',
    this.portRole,
    this.portSettings,
    this.tcpPort,
  });

  int? baud;

  String? flowControl;

  String? framing;

  String? linkSpeed;

  String? mac;

  String? operatingMode;

  String? portKind;

  String portLabel;

  String? portRole;

  String? portSettings;

  int? tcpPort;

  @override
  bool operator ==(Object other) => identical(this, other) || other is PortIn &&
    other.baud == baud &&
    other.flowControl == flowControl &&
    other.framing == framing &&
    other.linkSpeed == linkSpeed &&
    other.mac == mac &&
    other.operatingMode == operatingMode &&
    other.portKind == portKind &&
    other.portLabel == portLabel &&
    other.portRole == portRole &&
    other.portSettings == portSettings &&
    other.tcpPort == tcpPort;

  @override
  int get hashCode =>
    // ignore: unnecessary_parenthesis
    (baud == null ? 0 : baud!.hashCode) +
    (flowControl == null ? 0 : flowControl!.hashCode) +
    (framing == null ? 0 : framing!.hashCode) +
    (linkSpeed == null ? 0 : linkSpeed!.hashCode) +
    (mac == null ? 0 : mac!.hashCode) +
    (operatingMode == null ? 0 : operatingMode!.hashCode) +
    (portKind == null ? 0 : portKind!.hashCode) +
    (portLabel.hashCode) +
    (portRole == null ? 0 : portRole!.hashCode) +
    (portSettings == null ? 0 : portSettings!.hashCode) +
    (tcpPort == null ? 0 : tcpPort!.hashCode);

  @override
  String toString() => 'PortIn[baud=$baud, flowControl=$flowControl, framing=$framing, linkSpeed=$linkSpeed, mac=$mac, operatingMode=$operatingMode, portKind=$portKind, portLabel=$portLabel, portRole=$portRole, portSettings=$portSettings, tcpPort=$tcpPort]';

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{};
    if (this.baud != null) {
      json[r'baud'] = this.baud;
    } else {
      json[r'baud'] = null;
    }
    if (this.flowControl != null) {
      json[r'flow_control'] = this.flowControl;
    } else {
      json[r'flow_control'] = null;
    }
    if (this.framing != null) {
      json[r'framing'] = this.framing;
    } else {
      json[r'framing'] = null;
    }
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
    if (this.operatingMode != null) {
      json[r'operating_mode'] = this.operatingMode;
    } else {
      json[r'operating_mode'] = null;
    }
    if (this.portKind != null) {
      json[r'port_kind'] = this.portKind;
    } else {
      json[r'port_kind'] = null;
    }
      json[r'port_label'] = this.portLabel;
    if (this.portRole != null) {
      json[r'port_role'] = this.portRole;
    } else {
      json[r'port_role'] = null;
    }
    if (this.portSettings != null) {
      json[r'port_settings'] = this.portSettings;
    } else {
      json[r'port_settings'] = null;
    }
    if (this.tcpPort != null) {
      json[r'tcp_port'] = this.tcpPort;
    } else {
      json[r'tcp_port'] = null;
    }
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
        baud: mapValueOfType<int>(json, r'baud'),
        flowControl: mapValueOfType<String>(json, r'flow_control'),
        framing: mapValueOfType<String>(json, r'framing'),
        linkSpeed: mapValueOfType<String>(json, r'link_speed'),
        mac: mapValueOfType<String>(json, r'mac'),
        operatingMode: mapValueOfType<String>(json, r'operating_mode'),
        portKind: mapValueOfType<String>(json, r'port_kind'),
        portLabel: mapValueOfType<String>(json, r'port_label') ?? 'eth0',
        portRole: mapValueOfType<String>(json, r'port_role'),
        portSettings: mapValueOfType<String>(json, r'port_settings'),
        tcpPort: mapValueOfType<int>(json, r'tcp_port'),
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


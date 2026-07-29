import 'package:flutter_test/flutter_test.dart';
import 'package:sfa_mobile/models/user.dart';

AppUser user(String role, {bool restricted = false}) => AppUser(
      id: 1,
      username: role,
      fullName: role,
      email: '$role@example.test',
      role: role,
      isActive: true,
      canAccessRestrictedModules: restricted,
    );

void main() {
  test('field representative cannot open manager or procurement routes', () {
    final rep = user('field_rep');
    expect(rep.canAccessPath('/visit'), isTrue);
    expect(rep.canAccessPath('/order/new'), isTrue);
    expect(rep.canAccessPath('/order/primary'), isFalse);
    expect(rep.canAccessPath('/analytics/eis-mis'), isFalse);
    expect(rep.canAccessPath('/procurement/qc'), isFalse);
  });

  test('territory hierarchy can access manager routes but not vendor routes',
      () {
    final manager = user('territory_manager');
    expect(manager.canAccessPath('/order/primary'), isTrue);
    expect(manager.canAccessPath('/joint-working'), isTrue);
    expect(manager.canAccessPath('/procurement/vendor-admin'), isFalse);
  });

  test('vendor administrator is isolated to its procurement workspace', () {
    final vendorAdmin = user('vendor_admin');
    expect(vendorAdmin.landingPath, '/procurement/vendor-admin');
    expect(vendorAdmin.canAccessPath('/procurement/vendor-admin'), isTrue);
    expect(vendorAdmin.canAccessPath('/visit'), isFalse);
    expect(vendorAdmin.canAccessPath('/procurement/vendor-tech'), isFalse);
  });

  test('vendor technician is isolated to technician workflow', () {
    final technician = user('vendor_technician');
    expect(technician.landingPath, '/procurement/vendor-tech');
    expect(technician.canAccessPath('/procurement/vendor-tech'), isTrue);
    expect(technician.canAccessPath('/procurement/vendor-admin'), isFalse);
  });

  test('QC manager is isolated to QC workflow', () {
    final qc = user('qc_manager');
    expect(qc.landingPath, '/procurement/qc');
    expect(qc.canAccessPath('/procurement/qc'), isTrue);
    expect(qc.canAccessPath('/procurement/vendor-tech'), isFalse);
  });

  test('administrator can access all application routes', () {
    final admin = user('admin');
    for (final path in [
      '/visit',
      '/order/primary',
      '/analytics/eis-mis',
      '/procurement/qc',
      '/procurement/vendor-admin',
      '/procurement/vendor-tech',
    ]) {
      expect(admin.canAccessPath(path), isTrue, reason: path);
    }
  });

  test('explicit restricted-module entitlement permits manager features', () {
    final entitled = user('field_rep', restricted: true);
    expect(entitled.canAccessPath('/analytics/eis-mis'), isTrue);
    expect(entitled.canAccessPath('/order/primary'), isTrue);
  });
}

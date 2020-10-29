.. _elbv2_syntax_reference:

x-elbv2
=======


x-elbv2:
  AppLb:
    Properties: {}
    Settings:
      AssignSSlCert: True
    Services:
      - name: serviceA
        access: /
        port: 80
      - name: serviceB
        access: /anotherpath
        port: 80
      - name: serviceC
        port: 81


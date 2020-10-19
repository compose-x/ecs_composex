.. _s3_syntax_reference:

x-s3
=====

For the properties, go to to `AWS CFN S3 Definition`_

Services
--------

As for all other resource types, you can define the type of access you want based to the S3 buckets.
However, for buckets, this means distinguish the bucket and the objects resource.

Access types
^^^^^^^^^^^^

.. literalinclude:: ../ecs_composex/s3/s3_perms.json
    :language: json

Settings
--------

Some use-cases require special adjustments. This is what this section is for.

* `ExpandRegionToBucket`_
* `ExpandAccountIdToBucket`_
* `EnableEncryption`_

ExpandRegionToBucket
^^^^^^^^^^^^^^^^^^^^

When definining the `BucketName` in properties, if wanted to, for uniqueness or readability, you can append to that string
the region id (which is DNS compliant) to the bucket name.

.. code-block:: yaml

    Properties:
      BucketName: abcd-01
    Settings:
      ExpandRegionToBucket: True

Results into

.. code-block:: yaml

    !Sub abcd-01-${AWS::Region}

ExpandAccountIdToBucket
^^^^^^^^^^^^^^^^^^^^^^^

Similar to ExpandRegionToBucket, it will append the account ID (additional or instead of).

.. code-block:: yaml

    Properties:
      BucketName: abcd-01
    Settings:
      ExpandRegionToBucket: True

Results into

.. code-block:: yaml

    !Sub 'abcd-01-${AWS::AccountId}'

.. hint::

    If you set both ExpandAccountIdToBucket and ExpandRegionToBucket, you end up with

    .. code-block:: yaml

        !Sub 'abcd-01-${AWS::Region}-${AWS::AccountId}'

NameSeparator
^^^^^^^^^^^^^

As shown above, the separator between the bucket name and AWS::AccountId or AWS::Region is **-**. This parameter allows
you to define something else.

.. note::

    I would recommend not more than 2 characters separator.

.. warning::

    The separator must allow for DNS compliance **[a-z0-9.-]**


EnableEncryption
^^^^^^^^^^^^^^^^

If set to True (default) it will automatically define bucket encryption using AES256.

.. hint::

    Soon will link x-kms keys definition to that to allow you to re-use existing keys.


Lookup
------

The lookup allows you to find your cluster or db instance and also the Secret associated with them to allow ECS Services
to get access to these.

It will also find the DB security group and add an ingress rule.

.. code-block:: yaml

    x-s3:
      bucket-01:
        Lookup:
          Name: my-long-complicated-bucket-name
          Tags:
            - sometag: value


.. _AWS CFN S3 Definition: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-s3-bucket.html

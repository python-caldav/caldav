=================================
 Documentation: caldav |release|
=================================

help, I have forgotten how to write rst and I'm horrible at docs

.. code-block:: python

    from caldav.davclient import get_davclient

    with get_davclient() as client:
        my_principal = client.principal



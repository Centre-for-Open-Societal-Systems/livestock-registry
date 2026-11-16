"""Fill the farmer's personal details of existing livestock records from their approved
Farmer, once.

    python -m openg2p_registry_livestock_extension.profile_backfill --backfill

Run it in the staff-portal-api container after deploying the personal details
(farmer_reference/projection.py, zz-oan/96_record_farmer_profile.sql). New records
get them when they are written, and every active record of a Farmer when a change
to it is approved; this covers the ones written before. It is safe to run again: an
unchanged value is not rewritten, and a Farmer without a value leaves the record's
value as it is.

It sits at the package top level, so the staff API settings are loaded before the
register domain services are imported.
"""
import asyncio
import importlib
import sys


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backfill", action="store_true", required=True)
    parser.parse_args()
    module = __package__
    sys.modules.setdefault("openg2p_registry_extensions", importlib.import_module(module))
    importlib.import_module("openg2p_registry_staff_api.config").Settings.get_config()
    app = importlib.import_module(module + ".app")
    app.Initializer()
    from openg2p_fastapi_common.context import dbengine
    from sqlalchemy.ext.asyncio import async_sessionmaker

    projection = importlib.import_module(module + ".farmer_reference.projection")
    models = importlib.import_module("openg2p_registry_extensions.register_domain.models")

    async def run():
        engine = dbengine.get()
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                result = await projection.backfill_profiles(session, models.G2PRegisterFarmer,
                                                            models.G2PRegisterLivestock)
                await session.commit()
                return result
        finally:
            await engine.dispose()

    records, changed = asyncio.run(run())
    print(f"Personal details checked on {records} livestock record(s); {changed} updated from their Farmer.")


if __name__ == "__main__":
    main()

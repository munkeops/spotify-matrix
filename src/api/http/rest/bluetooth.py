"""Bluetooth device management routes (BlueZ via bluetoothctl)."""

from __future__ import annotations

from fastapi import APIRouter

from src.domain.models.api_schemas import (
    BluetoothActionRequest,
    BluetoothActionResponse,
    BluetoothDevicesResponse,
    BluetoothPowerRequest,
    BluetoothScanRequest,
    BluetoothStatusResponse,
)
from src.domain.services.bluetooth_service import bluetooth_service

router = APIRouter(tags=["assistant-matrix-bluetooth"])


@router.get("/api/bluetooth/status", response_model=BluetoothStatusResponse)
async def bluetooth_status() -> BluetoothStatusResponse:
    return BluetoothStatusResponse(**bluetooth_service.status())


@router.post("/api/bluetooth/power", response_model=BluetoothStatusResponse)
async def bluetooth_power(body: BluetoothPowerRequest) -> BluetoothStatusResponse:
    bluetooth_service.set_power(body.on)
    return BluetoothStatusResponse(**bluetooth_service.status())


@router.get("/api/bluetooth/devices", response_model=BluetoothDevicesResponse)
async def bluetooth_devices() -> BluetoothDevicesResponse:
    return BluetoothDevicesResponse(available=bluetooth_service.available(), devices=bluetooth_service.list_devices())


@router.post("/api/bluetooth/scan", response_model=BluetoothDevicesResponse)
async def bluetooth_scan(body: BluetoothScanRequest) -> BluetoothDevicesResponse:
    devices = bluetooth_service.scan(body.seconds)
    return BluetoothDevicesResponse(available=bluetooth_service.available(), devices=devices)


@router.post("/api/bluetooth/connect", response_model=BluetoothActionResponse)
async def bluetooth_connect(body: BluetoothActionRequest) -> BluetoothActionResponse:
    return BluetoothActionResponse(**bluetooth_service.connect(body.mac))


@router.post("/api/bluetooth/disconnect", response_model=BluetoothActionResponse)
async def bluetooth_disconnect(body: BluetoothActionRequest) -> BluetoothActionResponse:
    return BluetoothActionResponse(**bluetooth_service.disconnect(body.mac))


@router.post("/api/bluetooth/remove", response_model=BluetoothActionResponse)
async def bluetooth_remove(body: BluetoothActionRequest) -> BluetoothActionResponse:
    return BluetoothActionResponse(**bluetooth_service.remove(body.mac))

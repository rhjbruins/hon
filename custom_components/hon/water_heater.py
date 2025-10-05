import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.water_heater import (
    DEFAULT_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    WaterHeaterEntityDescription
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from pyhon.appliance import HonAppliance
from pyhon.parameter.range import HonParameterRange

from .const import DOMAIN, WH_MODE
from .entity import HonEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HonWaterHeaterEntityDescription(WaterHeaterEntityDescription):
    pass
    # mode: HVACMode = HVACMode.AUTO


WATERHEATERS: dict[
    str, tuple[HonWaterHeaterEntityDescription, ...]
] = {
    "HW": (
        HonWaterHeaterEntityDescription(
            key="settings",
            name="Hotwater boiler",
            icon="mdi:air-conditioner",
            translation_key="water_heater",
        ),
    )
    }


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    entities = []
    entity: HonWaterHeaterEntity
    for device in hass.data[DOMAIN][entry.unique_id]["hon"].appliances:
        for description in WATERHEATERS.get(device.appliance_type, []):
            if isinstance(description, HonWaterHeaterEntityDescription):
                if description.key not in list(device.commands):
                    continue
                entity = HonWaterHeaterEntity(hass, entry, device, description)
                continue  # type: ignore[unreachable]
            entities.append(entity)
    async_add_entities(entities)


class HonWaterHeaterEntity(HonEntity, WaterHeaterEntity):
    entity_description: HonWaterHeaterEntityDescription
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: HonAppliance,
        description: HonWaterHeaterEntityDescription,
    ) -> None:
        super().__init__(hass, entry, device, description)

        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._set_temperature_bound()

        self._attr_hvac_modes = []
        for mode in device.settings["settings.machMode"].values:
            self._attr_hvac_modes.append(WH_MODE[int(mode)])
        self._attr_preset_modes = []

        for mode in device.settings["startProgram.program"].values:
            self._attr_preset_modes.append(mode)
        
        self._handle_coordinator_update(update=False)

    def _set_temperature_bound(self) -> None:
        temperature = self._device.settings["settings.tempSel"]
        if not isinstance(temperature, HonParameterRange):
            raise ValueError
        self._attr_max_temp = temperature.max
        self._attr_target_temperature_step = temperature.step
        self._attr_min_temp = temperature.min

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._device.get("tempSel", 0.0)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._device.get("temp", 0.0)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        self._device.settings["settings.tempSel"].value = str(int(temperature))
        await self._device.commands["settings"].send()
        self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self, update: bool = True) -> None:
        if update:
            self.async_write_ha_state()

    @property
    def current_operation(self):
        """Return current operation ie. on, off."""
        return STATE_ON

    @property
    def operation_list(self):
        """Return the list of available fan modes."""
        fan_modes = []
        for mode in reversed(self._device.settings["settings.program"].values):
            fan_modes.append(WH_MODE[int(mode)])
        return fan_modes


    @property
    def min_temp(self):
        """Return the minimum targetable temperature."""
        """If the min temperature is not set on the config, returns the HA default for Water Heaters."""
        return self._attr_min_temp

    @property
    def max_temp(self):
        """Return the maximum targetable temperature."""
        """If the max temperature is not set on the config, returns the HA default for Water Heaters."""
        return self._attr_max_temp

    # async def async_set_operation_mode(self, operation_mode):
    #     """Set new operation mode."""
    #     self._current_operation = operation_mode
    #     await self._async_control_heating()

    # async def async_added_to_hass(self):
    #     """Run when entity about to be added."""
    #     await super().async_added_to_hass()

    #     self.async_on_remove(
    #         async_track_state_change_event(
    #             self.hass, [self.sensor_entity_id], self._async_sensor_changed
    #         )
    #     )
    #     self.async_on_remove(
    #         async_track_state_change_event(
    #             self.hass, [self.heater_entity_id], self._async_switch_changed
    #         )
    #     )

    #     old_state = await self.async_get_last_state()
    #     if old_state is not None:
    #         if old_state.attributes.get(ATTR_TEMPERATURE) is not None:
    #             self._target_temperature = float(old_state.attributes.get(ATTR_TEMPERATURE))
    #         self._current_operation = old_state.state

    #     temp_sensor = self.hass.states.get(self.sensor_entity_id)
    #     if temp_sensor and temp_sensor.state not in (
    #         STATE_UNAVAILABLE,
    #         STATE_UNKNOWN,
    #     ):
    #         self._current_temperature = float(temp_sensor.state)

    #     heater_switch = self.hass.states.get(self.heater_entity_id)
    #     if heater_switch and heater_switch.state not in (
    #         STATE_UNAVAILABLE,
    #         STATE_UNKNOWN,
    #     ):
    #         self._attr_available = True
    #     self.async_write_ha_state()

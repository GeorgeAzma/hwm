// Custom formatter for virtual memory display with used/total format
function formatVirtualMemory(usedValue) {
    if (isNaN(usedValue)) return '';

    // Get available virtual memory from the sensor
    const availableSensor = flatSensorData['/ram/data/3'];
    if (availableSensor && availableSensor.Value !== undefined) {
        let availableValue = parseValue(availableSensor.Value);
        if (!isNaN(availableValue)) {
            const totalValue = usedValue + availableValue;
            return `${usedValue.toFixed(1)} / ${totalValue.toFixed(0)}`;
        }
    }

    // Fallback to just showing used value if available is not available yet
    return usedValue.toFixed(1);
}

// Custom formatter for storage used space showing used/free GB
function formatStorageCapacity(usedPercentage, deviceName) {
    if (isNaN(usedPercentage)) return '';

    // Extract capacity from device name (e.g., "Samsung SSD 990 PRO 2TB" -> 2000, "WD Green SN350 1TB" -> 1000)
    const capacityMatch = deviceName.match(/(\d+(?:\.\d+)?)\s*(TB|GB)/i);
    if (capacityMatch) {
        let totalCapacityGB = parseFloat(capacityMatch[1]);
        const unit = capacityMatch[2].toUpperCase();

        // Convert TB to GB if needed
        if (unit === 'TB') {
            totalCapacityGB *= 1000;
        }

        const usedGB = (usedPercentage / 100) * totalCapacityGB;
        const freeGB = totalCapacityGB - usedGB;

        return `${usedGB.toFixed(0)} / ${totalCapacityGB.toFixed(0)}`;
    }

    // Fallback to percentage if capacity can't be extracted
    return `${usedPercentage.toFixed(1)}%`;
}

function formatPowerOnHours(hours) {
    if (isNaN(hours)) return '';

    const days = Math.floor(hours / 24);
    const remainingHours = hours % 24;

    if (days > 365) {
        const years = Math.floor(days / 365);
        const remainingDays = days % 365;
        return `${years}y ${remainingDays}d`;
    } else if (days > 0) {
        return `${days}d ${remainingHours}h`;
    } else {
        return `${hours}h`;
    }
}

// Export for use in other modules (if using modules)
// export { formatPowerOnHours };

// For browser compatibility, attach to window object
if (typeof window !== 'undefined') {
    window.formatPowerOnHours = formatPowerOnHours;
    window.formatStorageCapacity = formatStorageCapacity;
}

/*
 * Project : {{ project_name }}
 * Target  : {{ target }}
 * Created with analogdata-esp CLI · analogdata.io
 */

#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

void app_main(void)
{
    printf("[{{ project_name }}] Starting...\n");

    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}

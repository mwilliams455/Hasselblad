/* SPDX-License-Identifier: MIT */
#include "hb_phone_neutral_binding.h"
#include <stdlib.h>
#include <string.h>

int hb_phone_neutral_bind(const hb_phone_raw_grid *raw,
                          const hb_phone_domain_result *temperature_grid,
                          const hb_ns_capture_binding *meta,
                          hb_ns_frame *frame_out,hb_ns_domain *domain_out) {
    if (!raw || !temperature_grid || !meta || !frame_out || !domain_out)
        return HB_NS_BIND_ARGUMENT;
    if (!meta->original_single_raw_frame_proven ||
        !meta->physical_camera_and_result_frame_proven ||
        !meta->original_capture_color_metadata_proven ||
        !meta->original_sensor_timestamp_ns || !meta->original_exposure_time_ns ||
        !meta->original_ISO ||
        (meta->raw_statistics_basis!=HB_NS_BASIS_UNSHADED_SENSOR &&
         meta->raw_statistics_basis!=HB_NS_BASIS_HYPOTHETICAL_SHADED_STATISTICS))
        return HB_NS_BIND_UNPROVEN;
    if (temperature_grid->schema_version!=HB_PHONE_DOMAIN_SCHEMA ||
        temperature_grid->point_count<1 ||
        temperature_grid->point_count>HB_NS_MAX_KNOTS ||
        !temperature_grid->kelvin_count || !temperature_grid->tint_count ||
        temperature_grid->kelvin_count>81 || temperature_grid->tint_count>9 ||
        temperature_grid->kelvin_count*temperature_grid->tint_count!=
          temperature_grid->point_count ||
        temperature_grid->representable+
          temperature_grid->temperature_clipped+
          temperature_grid->scene_signed_gain+
          temperature_grid->adjacent_duplicate!=temperature_grid->point_count)
        return HB_NS_BIND_DOMAIN_INVALID;
    uint32_t counted[4]={0};
    for (uint32_t i=0;i<temperature_grid->point_count;++i) {
        const hb_phone_domain_point *k=&temperature_grid->points[i];
        if (k->exclusion>HB_PHONE_DOMAIN_ADJACENT_DUPLICATE) return HB_NS_BIND_DOMAIN_INVALID;
        ++counted[k->exclusion];
        if (k->exclusion==HB_PHONE_DOMAIN_REPRESENTABLE) {
            if (!k->gain_q12[0] || k->gain_q12[1]!=4096 ||
                !k->gain_q12[2]) return HB_NS_BIND_DOMAIN_INVALID;
        } else if (k->gain_q12[0] || k->gain_q12[1] || k->gain_q12[2])
            return HB_NS_BIND_DOMAIN_INVALID;
    }
    if (counted[0]!=temperature_grid->representable ||
        counted[1]!=temperature_grid->temperature_clipped ||
        counted[2]!=temperature_grid->scene_signed_gain ||
        counted[3]!=temperature_grid->adjacent_duplicate)
        return HB_NS_BIND_DOMAIN_INVALID;
    uint32_t valid_raw=0;
    for (uint32_t i=0;i<HB_NS_BLOCK_COUNT;++i) {
        const hb_phone_block *b=&raw->blocks[i];
        if (b->flags & ~7u) return HB_NS_BIND_RAW_INVALID;
        if (!b->flags) ++valid_raw;
    }
    if (valid_raw != raw->ratio_blocks) return HB_NS_BIND_RAW_INVALID;
    hb_ns_frame *f=calloc(1,sizeof(*f));
    hb_ns_domain *d=calloc(1,sizeof(*d));
    if (!f || !d) {free(f);free(d);return HB_NS_BIND_MEMORY;}
    f->sensor_timestamp_ns=meta->original_sensor_timestamp_ns;
    f->exposure_time_ns=meta->original_exposure_time_ns;
    f->ISO=meta->original_ISO;
    f->bound_to_physical_sensor_and_frame=1;
    f->original_single_raw_proven=1;
    f->basis=meta->raw_statistics_basis;
    for (uint32_t i=0;i<HB_NS_BLOCK_COUNT;++i) {
        const hb_phone_block *src=&raw->blocks[i];
        hb_ns_block *dest=&f->blocks[i];
        for(int j=0;j<4;++j)dest->mean[j]=src->mean[j];
        dest->mean_brightness=src->mean_brightness;
        dest->red_gain_q12=src->red_gain_q12;
        dest->blue_gain_q12=src->blue_gain_q12;
        dest->raw_flags=src->flags;
    }
    d->schema=HB_NS_SCHEMA;
    d->count=temperature_grid->point_count;
    for (uint32_t i=0;i<d->count;++i) {
        const hb_phone_domain_point *src=&temperature_grid->points[i];
        hb_ns_knot *dest=&d->points[i];
        dest->kelvin=src->kelvin;
        dest->tint=src->tint;
        dest->exclusion=src->exclusion;
        dest->red_gain_q12=src->gain_q12[0];
        dest->blue_gain_q12=src->gain_q12[2];
    }
    *frame_out=*f;
    *domain_out=*d;
    free(f);free(d);
    return HB_NS_BIND_OK;
}

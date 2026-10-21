#include "hb_awb_recalib.h"

static hb_awb_recalib_result checked_input(hb_awb_q12_pair input,
                                          hb_awb_q12_pair calibration)
{
    hb_awb_recalib_result result;
    result.adapter_status = HB_AWB_OK;
    result.original_status = 0;
    result.original_called = 0;
    result.output = input;
    if (calibration.a == 0 || calibration.b == 0) {
        result.adapter_status = HB_AWB_ZERO_CALIBRATION;
    } else if (input.a > HB_AWB_MAX_SAFE_GAIN || input.b > HB_AWB_MAX_SAFE_GAIN) {
        result.adapter_status = HB_AWB_GAIN_OVERFLOW;
    }
    return result;
}

hb_awb_recalib_result hb_awb_recalib_portable(hb_awb_q12_pair input,
                                            hb_awb_q12_pair calibration)
{
    hb_awb_recalib_result result = checked_input(input, calibration);
    if (result.adapter_status != HB_AWB_OK) {
        return result;
    }
    /* The guards establish that these original-width shifts cannot overflow. */
    result.output.a = (input.a << 12) / calibration.a;
    result.output.b = (input.b << 12) / calibration.b;
    return result;
}

hb_awb_recalib_result hb_awb_recalib_original(hb_awb_original_recalib_fn original,
                                            hb_awb_q12_pair input,
                                            hb_awb_q12_pair calibration)
{
    hb_awb_recalib_result result = checked_input(input, calibration);
    hb_awb_q12_pair work = input;
    if (result.adapter_status != HB_AWB_OK) {
        return result;
    }
    if (original == 0) {
        result.adapter_status = HB_AWB_ORIGINAL_MISSING;
        return result;
    }
    result.original_called = 1;
    result.original_status = original(&work.a, &work.b,
                                      calibration.a, calibration.b);
    if (result.original_status != 0) {
        result.adapter_status = HB_AWB_ORIGINAL_REJECTED;
        return result;
    }
    result.output = work;
    return result;
}
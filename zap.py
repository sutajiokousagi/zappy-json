#!/usr/bin/python3

import json
import argparse
import socket
import telnetlib
import matplotlib.pyplot as plt
from datetime import datetime
import csv

#test_parsed = json.loads(test)
#test_voltage = test_parsed["voltage"].split(':')
ENERGY_COEFF = 1.691356e-9
ONEJOULE = 591241583.67

class ZappyJSON():
    def __init__(self, target_ip="10.0.11.2", dry_run=False, verbose=False, prefix=None, no_png=False, serialize=False):
        self.target_ip = target_ip
        self.dry_run = dry_run
        self.verbose = verbose
        self.prefix = prefix
        self.no_png = no_png
        self.serialize = serialize

    def zap_inner(self, command):
        voltage = command["voltage"].split(':')
        if voltage[1].lower() != 'volts':
            print('Voltage units are not recognized')
            exit(1)
        v = float(voltage[0])
        if v > 1000.0 or v < 12.0:  # minimum voltage is 10 for now due to discharge thresholds
            print('Voltage ' + v + ' out of range')
            exit(1)

        duration = command["duration"].split(':')
        if duration[1].lower() != 'milliseconds':
            print('Duration units are not recognized')
            exit(1)
        time = float(duration[0])
        if time > 15.3 or time < 0.0:
            print('Duration ' + 'ms out of range')
            exit(1)
        else:
            time = time + 1.0  # there is a 1.0ms "pre-amble" in the dataset

        # set to invalid negatives so we can detect if any defaults are overriden
        row = -1
        col = -1
        max_current = 16.0  # this is the max safe operating current of the transistors
        energy_cutoff = 0  # 0 means don't use energy cutoff

        if 'option' in command:
            options = command["option"]

            if 'row' in options:
                row = int(options["row"])
                if row < 1 or row > 5:
                    print("Row " + str(row) + " out of range")
                    exit(1)
                row = row - 1  # actual row is zero-offset for zappy
            if 'col' in options:
                col = int(options["col"])
                if col < 1 or col > 13:
                    print("Col " + str(col) + " out of range")
                    exit(1)
                col = col - 1  # actual col is zero-offset for zappy
            if 'max_current' in options:
                maxc = options["max_current"].split(':')
                if maxc[1].lower() != 'amp' and maxc[1].lower() != 'amps':
                    print("Units not recognized for max_current")
                    exit(1)
                max_current = float(maxc[0])
                if max_current < 0.0:
                    if self.verbose:
                        print("Max current is negative - anti-arc is disabled")
            if 'energy_cutoff' in options:
                ecut = options["energy_cutoff"].split(':')
                if ecut[1].lower() != 'joules' and ecut[1].lower() != 'joule':
                    print("Units not recognized for energy_cutoff")
                    exit(1)
                energy_cutoff_joules = float(ecut[0])
                energy_cutoff = int(energy_cutoff_joules * ONEJOULE)
                if energy_cutoff > 4294967295:
                    print("Energy cutoff 32-bit integer overflow")
                    exit(1)
                if self.verbose:
                    print("Setting cutoff of " + str(energy_cutoff) + " counts")

        if row == -1:
            print("Warning: no row specified, defaulting to all rows")
            row = 4
        if col == -1:
            print("Warning: no col specified, defaulting to all columns")
            col = 12

        if self.dry_run or self.verbose:
            print('Parsing successful: voltage ' + str(v) + ' duration ' + str(time) + ' row ' + str(
                row + 1) + ' col ' + str(col + 1) + ' max_current ' + str(max_current) + ' energy_cutoff ' + str(
                energy_cutoff))
            if self.dry_run:
                return

        try:
            tn = telnetlib.Telnet(self.target_ip)
            zapstr = str('zap ' + str(row) + ' ' + str(col) + ' ' + str(v) + ' ' + str(time * 1000) + ' ' + str(
                max_current * 1000) + ' ' + str(energy_cutoff) + '\n\r')
            if self.verbose:
                print('telnet> ' + zapstr)
            zapbytes = bytearray(zapstr, 'utf-8')
            tn.write(bytes(zapbytes))

            try:
                ret = tn.expect(["zerr", "zpass"], timeout=10)
                # this requires editing telnetlib.py expect function: dm = list[i].search(self.cookedq.decode('utf-8'))
            except EOFError:
                print('Zappy.zap failed: no status return')
            if ret[0] == -1:
                print('Zappy.zap failed: status return timeout')

            if self.verbose and ret[0] != -1:
                print('DEBUG: ' + ret[2].decode('utf-8'))

            if ret[2].decode('utf-8').find('zpass') != -1:
                tn.close()
                self.dump_csv(row + 1, col + 1, v, time)
                return
            else:
                print('Chassis returned error')
                print(ret[2].decode('utf-8'))
                tn.close()
                exit(1)

        except Exception as e:
            print(e)
            print('Error sending command to zappy logic module')

    def zap(self, json_string):
        self.json_string = json_string

        try:
            command = json.loads(self.json_string)
        except Exception as e:
            print(e)
            print('JSON grammar error decoding input string')
            exit(1)

        try:
            if(command["name"] == 'Zappy.zap'):
                self.zap_inner(command)

            elif(command["name"] == 'Zappy.lock'):
                if self.dry_run:
                    print('Dry run got lock command')
                else:
                    try:
                        tn = telnetlib.Telnet(self.target_ip)
                        zapstr = str('plate lock\n\r')
                        if self.verbose:
                            print('telnet> ' + zapstr)
                        zapbytes = bytearray(zapstr, 'utf-8')
                        tn.write(bytes(zapbytes))
                        try:
                            ret = tn.expect(["zerr", "zpass"], timeout=10)
                            # this requires editing telnetlib.py expect function: dm = list[i].search(self.cookedq.decode('utf-8'))
                        except EOFError:
                            print('Zappy.lock failed: no status return')
                        if ret[0] == -1:
                            print('Zappy.lock failed: status return timeout')

                        if self.verbose and ret[0] != -1:
                            print('DEBUG: ' + ret[2].decode('utf-8'))

                        if ret[2].decode('utf-8').find('zpass') != -1:
                            tn.close()
                            exit(0)
                        else:
                            print('Chassis returned error')
                            print(ret[2].decode('utf-8'))
                            tn.close()
                            exit(1)

                    except Exception as e:
                        print(e)
                        print('Error sending command to zappy logic module')

            elif(command["name"] == 'Zappy.unlock'):
                if self.dry_run:
                    print('Dry run got unlock command')
                else:
                    try:
                        tn = telnetlib.Telnet(self.target_ip)
                        zapstr = str('plate unlock\n\r')
                        if self.verbose:
                            print('telnet> ' + zapstr)
                        zapbytes = bytearray(zapstr, 'utf-8')
                        tn.write(bytes(zapbytes))
                        try:
                            ret = tn.expect(["zerr", "zpass"], timeout=10)
                            # this requires editing telnetlib.py expect function (line 620): m = list[i].search(self.cookedq.decode('utf-8'))
                        except EOFError:
                            print('Zappy.lock failed: no status return')
                        if ret[0] == -1:
                            print('Zappy.lock failed: status return timeout')

                        if self.verbose and ret[0] != -1:
                            print('DEBUG: ' + ret[2].decode('utf-8'))

                        if ret[2].decode('utf-8').find('zpass') != -1:
                            tn.close()
                            exit(0)
                        else:
                            print('Chassis returned error')
                            print(ret[2].decode('utf-8'))
                            tn.close()
                            exit(1)

                    except Exception as e:
                        print(e)
                        print('Error sending command to zappy logic module')
            else:
                print("Command " + command["name"] + "not recognized")
                exit(1)
        except KeyError:
            print("No 'name' field in JSON record, aborting")
            exit(1)

    def hex_to_signed(self, source):
        """Convert a string hex value to a signed hexadecimal value.

        This assumes that source is the proper length, and the sign bit
        is the first bit in the first byte of the correct length.

        hex_to_signed("F") should return -1.
        hex_to_signed("0F") should return 15.
        """
        if not isinstance(source, str):
            raise ValueError("string type required")
        if 0 == len(source):
            raise valueError("string is empty")
        sign_bit_mask = 1 << (len(source) * 4 - 1)
        other_bits_mask = sign_bit_mask - 1
        value = int(source, 16)
        return -(value & sign_bit_mask) | (value & other_bits_mask)

    # row and col are 1-based numbering
    def dump_csv(self, row, col, v, time):
        if self.prefix is None:
            return

        in_prefix = '/opt/zappy/zappy-log.'
        energy_prefix = '/opt/zappy/zappy-energy.'
        if row == 5:
            rstart = 1
            rstop = 5
        else:
            rstart = row
            rstop = row+1

        if col == 13:
            cstart = 1
            cstop = 13
        else:
            cstart = col
            cstop = col+1

        slow = []
        fast = []

        # hard coded calibration parameters from zappy-01 for now
        FAST_M=230.156015 #215.7720466
        FAST_B=0.176922133 #-0.0488699
        SLOW_M=229.9235716
        SLOW_B=-0.008779325
        P5V_ADC=5.009
        for r in range(rstart, rstop):
            for c in range(cstart, cstop):
                with open(in_prefix + 'r' + str(r) + 'c' + str(c), "rb") as f:
                    s = f.read(2)
                    while s:
                        slow.append(int.from_bytes(s, byteorder='little'))
                        s = f.read(2)
                        fast.append(int.from_bytes(s, byteorder='little'))
                        s = f.read(2)

                with open(energy_prefix + 'r' + str(r) + 'c' + str(c), "r") as ef:
                    s = ef.read()
                    energycode = self.hex_to_signed(s.rstrip())

                if self.serialize:
                    now = datetime.now()
                    out_name = self.prefix + now.strftime("%Y_%b_%d-%H_%M_%S.%f")[:-3] + '-r' + str(r) + 'c' + str(c) + '.csv'
                else:
                    out_name = self.prefix + 'r' + str(r) + 'c' + str(c) + '.csv'

                slowg = []
                fastg = []
                with open(out_name, "w") as outf:
                    print("warning: using hard-coded calibration parameters from zappy-01", file=outf)
                    print("measured energy, " + str(energycode) + ", counts, " + str(energycode * ENERGY_COEFF) + ", joules", file=outf)
                    print("row, " + str(r) + ", col, " + str(c) + ", target V, " + str(v), file=outf)
                    print("slow V, fast V, slow code, fast code", file=outf)
                    for i in range(len(slow)):
                        slowv = (slow[i] * (P5V_ADC / 4096) - P5V_ADC / 8192) * SLOW_M + SLOW_B
                        slowg.append(slowv)
                        fastv = (fast[i] * (P5V_ADC / 4096) - P5V_ADC / 8192) * FAST_M + FAST_B
                        fastg.append(fastv)
                        print(str(slowv) + ', ' + str(fastv) + ', ' + str(slow[i]) + ', ' + str(fast[i]), file=outf)
                    outf.close()

                if self.no_png == False:
                    t = range(len(slowg))
                    axismax = max(slowg)
                    if( axismax < max(fastg)):
                        axismax = max(fastg)
                    plt.plot(t, fastg, 'b', label='on cell', alpha=0.5)
                    plt.plot(t, slowg, 'r', label='at cap', alpha=0.5)
                    plt.ylim(0, axismax)
                    plt.title('Zappy: row ' + str(r) + ' / col ' + str(c) + '/ target ' + str(v) + 'V / duration ' + str(time - 1.0) + 'ms + 1.0ms preamble; ' + '%.3f' % (energycode * ENERGY_COEFF) + 'J / ' + 'calparams: zappy-01', fontsize=8)
                    plt.xlabel('time us')
                    plt.ylabel('volts V')
                    plt.legend(loc='lower right')
                    if self.serialize:
                        out_png = self.prefix + now.strftime("%Y_%b_%d-%H_%M_%S.%f")[:-3] + '-r' + str(r) + 'c' + str(c) + '.png'
                    else:
                        out_png = self.prefix + 'r' + str(r) + 'c' + str(c) + '.png'
                    plt.savefig(out_png, dpi=300)
                    plt.clf()

                slow = []
                fast = []
                f.close()





def main():
    parser = argparse.ArgumentParser(description="Zappy JSON command line interface")
    parser.add_argument(
        "-t", "--target", help="IP address of zappy logic board", default="10.0.11.2"
    )
    filetype = parser.add_mutually_exclusive_group(required=True)
    filetype.add_argument(
        "-f", "--file", help="Filename of JSON command"
    )
    filetype.add_argument(
        "-c", "--csv", help="Filename of CSV command file"
    )
    parser.add_argument(
        "-d", "--dry-run", help="Dry run to check input formatting", dest='dry_run', action='store_true'
    )
    parser.add_argument(
        "-v", "--verbose", help="Print debugging spew", dest='verbose', action='store_true'
    )
    parser.add_argument(
        "-p", "--prefix", help="Output file prefix for saving CSV and PNG"
    )
    parser.add_argument(
        "-n", "--no-png", help="Don't save PNG graph when output prefix is specified to speedup data post-processing", dest='no_png', action='store_true'
    )
    parser.add_argument(
        "-s", "--serialize", help="Add timestamps to filename when saving CSV and PNG", dest='serialize', action='store_true'
    )
    parser.set_defaults(dry_run=False)
    parser.set_defaults(verbose=False)
    parser.set_defaults(no_png=False)
    parser.set_defaults(serialize=False)
    args = parser.parse_args()

    try:
        socket.inet_aton(args.target)
        target_ip = args.target
    except socket.error:
        print('IP ' + args.target + ' is not valid')
        exit(1)

    if args.file:
        json_file = args.file

        try:
            f = open(json_file, 'rb')
        except IOError:
            print('Error opening file ' + json_file)
            exit(1)

        with f:
            json_string = f.read()
            zappy = ZappyJSON(target_ip, args.dry_run, args.verbose, args.prefix, args.no_png, args.serialize)
            zappy.zap(json_string)
            exit(0)

    elif args.csv:
        csv_file = args.csv

        try:
            with open(csv_file, newline='') as f:
                reader = csv.DictReader(f)
                zappy = ZappyJSON(target_ip, args.dry_run, args.verbose, args.prefix, args.no_png, args.serialize)

                for row in reader:
                    command = {}
                    command['voltage'] = str(row['voltage']) + ':volts'
                    command['duration'] = str(row['duration']) + ':milliseconds'
                    option={}
                    option['row'] = str(row['row'])
                    option['col'] = str(row['col'])
                    option['max_current'] = str(row['max_current']) + ':amps'
                    option['energy_cutoff'] = str(row['energy_cutoff']) + ':joules'
                    command['option'] = option
                    zappy.zap_inner(command)

                exit(0)

        except IOError:
            print('Error opening file ' + csv_file)
            exit(1)


if __name__ == "__main__":
    main()

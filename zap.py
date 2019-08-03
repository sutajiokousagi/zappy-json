#!/usr/bin/python3

import json
import argparse
import socket
import telnetlib


#test_parsed = json.loads(test)
#test_voltage = test_parsed["voltage"].split(':')

class ZappyJSON():
    def __init__(self, json_string, target_ip="10.0.11.2", dry_run=False, verbose=False):
        self.json_string = json_string
        self.target_ip = target_ip
        self.dry_run = dry_run
        self.verbose = verbose

    def zap(self):
        try:
            command = json.loads(self.json_string)
        except Exception as e:
            print(e)
            print('JSON grammar error decoding input string')
            exit(1)

        try:
            if(command["name"] == 'Zappy.zap'):
                voltage = command["voltage"].split(':')
                if voltage[1].lower() != 'v':
                    print('Voltage units are not recognized')
                    exit(1)
                v = float(voltage[0])
                if v > 1000.0 or v < 12.0:  # minimum voltage is 10 for now due to discharge thresholds
                    print('Voltage ' + v + ' out of range')
                    exit(1)

                duration = command["duration"].split(':')
                if duration[1].lower() != 'ms':
                    print('Duration units are not recognized')
                    exit(1)
                time = float(duration[0])
                if time > 16.3 or time < 0.0:
                    print('Duration ' + 'ms out of range')
                    exit(1)

                # set to invalid negatives so we can detect if any defaults are overriden
                row = -1
                col = -1
                max_current = -1.0

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
                        col = col - 1 # actual col is zero-offset for zappy
                    if 'max_current' in options:
                        maxc = options["max_current"].split(':')
                        if maxc[1].lower() != 'amp':
                            print("Units not recognized for max_current")
                            exit(1)
                        max_current = float(maxc[0])
                        if max_current < 0.0:
                            print("Max current out of range")
                            exit(1)

                if row == -1:
                    print("Warning: no row specified, using default of 1")
                    row = 1
                if col == -1:
                    print("Warning: no col specified, using default of 1")
                    col = 1
                if max_current == -1.0:
                    # no warning emitted because this is not really a common parameter to specify
                    max_current = 100.0  # just specify a big number, should always be less than this

                if self.dry_run or self.verbose:
                    print('Parsing successful: voltage '+ str(v) + ' duration ' + str(time) + ' row ' + str(row+1) + ' col ' + str(col+1) + ' max_current ' + str(max_current) )
                    if self.dry_run:
                        exit(1)

                try:
                    tn = telnetlib.Telnet(self.target_ip)
                    zapstr = str('zap ' + str(row) + ' ' + str(col) + ' ' + str(v) + ' ' + str(time * 1000) + '\n\r')
                    if self.verbose:
                        print('telnet> ' + zapstr)
                    zapbytes = bytearray(zapstr,'utf-8')
                    tn.write(bytes(zapbytes))
                    retstr = str(tn.read_until(bytearray('data', 'utf-8'), timeout=2))
                    if self.verbose:
                        print(retstr)
                    tn.close()

                except Exception as e:
                    print(e)
                    print('Error sending command to zappy logic module')


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

                        if ret[2].decode('utf-8').find('zpass'):
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
                            # this requires editing telnetlib.py expect function: dm = list[i].search(self.cookedq.decode('utf-8'))
                        except EOFError:
                            print('Zappy.lock failed: no status return')
                        if ret[0] == -1:
                            print('Zappy.lock failed: status return timeout')

                        if self.verbose and ret[0] != -1:
                            print('DEBUG: ' + ret[2].decode('utf-8'))

                        if ret[2].decode('utf-8').find('zpass'):
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


def main():
    parser = argparse.ArgumentParser(description="Zappy JSON command line interface")
    parser.add_argument(
        "-t", "--target", help="IP address of zappy logic board", default="10.0.11.2"
    )
    parser.add_argument(
        "-f", "--file", help="Filename of JSON command", default="zap.json",
    )
    parser.add_argument(
        "-d", "--dry-run", help="Dry run to check JSON formatting", dest='dry_run', action='store_true'
    )
    parser.add_argument(
        "-v", "--verbose", help="Print debugging spew", dest='verbose', action='store_true'
    )
    parser.set_defaults(dry_run=False)
    parser.set_defaults(verbose=False)
    args = parser.parse_args()

    try:
        socket.inet_aton(args.target)
        target_ip = args.target
    except socket.error:
        print('IP ' + args.target + ' is not valid')
        exit(1)

    json_file = args.file

    try:
        f = open(json_file, 'rb')
    except IOError:
        print('Error opening file ' + json_file)
        exit(1)

    with f:
        json_string = f.read()
        zappy = ZappyJSON(json_string, target_ip, args.dry_run, args.verbose)
        zappy.zap()
        exit(0)

if __name__ == "__main__":
    main()

#!/bin/bash

row=1
col=1

until [ $row -gt 4 ]
do
    col=1
    until [ $col -gt 12 ]
    do
	touch zappy-log.r${row}c${col}
	((col++))
    done
    ((row++))
done

       
